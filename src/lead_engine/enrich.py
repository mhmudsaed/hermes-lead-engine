"""Core enrichment engine: homepage -> careers -> about per company.

Each company is enriched inside its own isolated browser context
(``site_tag`` = slug of the company), so cookies/state never leak between
sites and a failure on one company only marks that row failed — the run
always continues. Fields without a verified source stay EMPTY (never
guessed). CAPTCHA/login walls abort that row cleanly with a logged reason.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from lead_engine.browser import BlockedPage, BrowserAdapter, PageSnapshot
from lead_engine.csv_input import InputRow
from lead_engine.outreach import draft_outreach
from lead_engine.tech_signals import parse_tech_signals
from lead_engine.url_rules import (
    is_about_url,
    is_careers_url,
    is_contact_url,
    pick_about_link,
    pick_careers_link,
    pick_contact_link,
    same_site,
)

MAX_PAGES_PER_COMPANY = 6

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_WS_RE = re.compile(r"\s+")
# Placeholder / infrastructural addresses that are never real contacts.
# NOTE: bare ".example" (RFC 2606 reserved TLD, used by the synthetic
# fixture site) is deliberately NOT junk — only example.com/org/net are.
_JUNK_DOMAINS = frozenset({"example.com", "example.org", "example.net"})
_JUNK_LOCALPARTS = ("noreply", "no-reply", "donotreply", "do-not-reply", "test", "sentry", "wixpress")
_JUNK_SUBSTRINGS = ("godaddy", "sentry", "wixpress")


def slugify(company: str) -> str:
    """Filesystem/URL-safe slug: lowercase, non-alnum runs become '-'."""
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    return slug or "company"


def resolve_start_url(domain: str, base_url_template: str = "") -> str:
    """Turn an input ``domain`` token into an absolute start URL.

    - Already absolute (``http(s)://...``) -> used as-is.
    - ``host:port[/path]`` or ``host/path`` -> ``http://`` prefixed.
    - Bare token (fixture slug) with a template -> template expanded,
      ``{slug}`` / ``{domain}`` placeholders supported.
    - Otherwise -> ``https://`` prefixed (live mode).
    """
    domain = domain.strip()
    if domain.startswith(("http://", "https://")):
        return domain
    if base_url_template:
        template = base_url_template
        for placeholder in ("{slug}", "{domain}"):
            template = template.replace(placeholder, slugify(domain))
        return template
    if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*:\d{1,5}(/.*)?$", domain):
        return "http://" + domain
    if "/" in domain:
        return "http://" + domain
    return "https://" + domain


def _is_junk_email(address: str) -> bool:
    """True for placeholder/infrastructural addresses (never real contacts)."""
    lowered = address.lower()
    if "@" not in lowered:
        return True
    local, _, domain = lowered.partition("@")
    if domain in _JUNK_DOMAINS:
        return True
    if any(local == part or local.startswith(part + "+") for part in _JUNK_LOCALPARTS):
        return True
    if any(j in lowered for j in _JUNK_SUBSTRINGS):
        return True
    return False


def extract_emails(text: str) -> list[str]:
    """Published emails found in page text (untrusted data, returned verbatim).

    Filters obvious junk/placeholder addresses; order-preserving dedupe.
    """
    seen: set[str] = set()
    found: list[str] = []
    for match in _EMAIL_RE.findall(text or ""):
        lowered = match.lower()
        if _is_junk_email(lowered):
            continue
        if lowered not in seen:
            seen.add(lowered)
            found.append(match)
    return found


def summarize(text: str, max_chars: int = 220) -> str:
    """One-line summary: first substantial sentence-ish chunk of page text."""
    cleaned = _WS_RE.sub(" ", (text or "").strip())
    if not cleaned:
        return ""
    snippet = ""
    for chunk in re.split(r"(?<=[.!?])\s+", cleaned):
        stripped = chunk.strip()
        # Skip stubs ("Hi.") so thin pages don't produce a fake summary.
        if len(stripped) >= 40:
            snippet = stripped
            break
    if not snippet:
        return ""
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rsplit(" ", 1)[0] + "..."
    return snippet


@dataclass
class CompanyResult:
    """Enriched row for one company."""

    company: str
    domain: str
    notes: str = ""
    status: str = "failed"  # enriched | failed | blocked | skipped
    homepage_url: str = ""
    careers_url: str = ""
    about_url: str = ""
    contact: str = ""
    tech_signals: list[str] = field(default_factory=list)
    summary: str = ""
    outreach_draft: str = ""
    screenshot_path: str = ""
    source_urls: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class RunReport:
    """Aggregate outcome of a run."""

    processed: int = 0
    enriched: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass
class EngineConfig:
    """Tunable run parameters."""

    base_url_template: str = ""
    screenshots_dir: str = "screenshots"
    max_pages_per_company: int = MAX_PAGES_PER_COMPANY
    llm_polish: bool = False
    limit: int = 0  # 0 = no limit


def _site_tag(company: str) -> str:
    return slugify(company)


def enrich_one(
    row: InputRow,
    browser: BrowserAdapter,
    config: EngineConfig,
) -> CompanyResult:
    """Enrich a single company. Never raises: all failures become a result."""
    result = CompanyResult(company=row.company, domain=row.domain, notes=row.notes)
    tag = _site_tag(row.company)
    try:
        return _enrich_inner(row, browser, config, result, tag)
    except BlockedPage as exc:
        result.status = "blocked"
        result.reason = str(exc)
        return result
    except Exception as exc:  # per-row isolation: never take down the run
        result.status = "failed"
        result.reason = f"unexpected error: {exc}"
        return result


def _enrich_inner(
    row: InputRow,
    browser: BrowserAdapter,
    config: EngineConfig,
    result: CompanyResult,
    tag: str,
) -> CompanyResult:
    start_url = resolve_start_url(row.domain, config.base_url_template)
    home = browser.visit(start_url, tag)
    if not home.ok:
        result.reason = f"homepage unreachable: {home.error or home.status}"
        return result
    result.homepage_url = home.url
    result.source_urls.append(home.url)

    try:
        base_netloc = urlparse(home.url).netloc
    except ValueError:
        result.reason = f"homepage URL unparsable: {home.url!r}"
        return result

    pages_fetched = 1
    # -- careers ------------------------------------------------------
    careers_url = home.url if is_careers_url(home.url) else None
    if careers_url is None:
        careers_url = pick_careers_link(home.links, base_netloc)
    careers_text = ""
    if careers_url and pages_fetched < config.max_pages_per_company:
        try:
            snap = browser.visit(careers_url, tag)
            pages_fetched += 1
            if snap.ok and (is_careers_url(snap.url) or snap.url == careers_url):
                careers_url = snap.url
                careers_text = snap.text
                result.source_urls.append(snap.url)
            else:
                careers_url = None  # candidate did not verify as reachable careers page
        except BlockedPage:
            raise
        except Exception:
            careers_url = None
    if careers_url:
        result.careers_url = careers_url

    # -- about ----------------------------------------------------------
    about_url = home.url if is_about_url(home.url) else None
    if about_url is None:
        about_url = pick_about_link(home.links, base_netloc)
    about_text = ""
    if about_url and about_url != careers_url and pages_fetched < config.max_pages_per_company:
        try:
            snap = browser.visit(about_url, tag)
            pages_fetched += 1
            if snap.ok:
                about_url = snap.url
                about_text = snap.text
                result.source_urls.append(snap.url)
            else:
                about_url = None
        except BlockedPage:
            raise
        except Exception:
            about_url = None
    if about_url:
        result.about_url = about_url

    # -- contact: mailto links, then contact pages, then visible emails --
    contact = ""
    mailtos = sorted(
        {
            href[7:].split("?")[0]
            for href, _text in home.links
            if href.lower().startswith("mailto:")
            and "@" in href
            and not _is_junk_email(href[7:].split("?")[0])
        }
    )
    if mailtos:
        contact = mailtos[0]
    contact_page_url: str | None = None
    if not contact:
        contact_page_url = pick_contact_link(home.links, base_netloc)
        if (
            contact_page_url
            and contact_page_url not in (careers_url, about_url)
            and pages_fetched < config.max_pages_per_company
        ):
            try:
                snap = browser.visit(contact_page_url, tag)
                pages_fetched += 1
                if snap.ok:
                    result.source_urls.append(snap.url)
                    emails = extract_emails(snap.text)
                    contact = emails[0] if emails else ""
                    if not contact and is_contact_url(snap.url):
                        contact = snap.url
            except BlockedPage:
                raise
            except Exception:
                contact_page_url = None
        elif contact_page_url and is_contact_url(contact_page_url):
            contact = contact_page_url  # page known from nav, budget spent
    if not contact:
        for blob in (home.text, about_text, careers_text):
            emails = extract_emails(blob)
            if emails:
                contact = emails[0]
                break
    if not contact and (
        contact_page_url
        or any(is_contact_url(href) for href, _t in home.links if same_site(href, base_netloc))
    ):
        contact = contact_page_url or next(
            href for href, _t in home.links
            if is_contact_url(href) and same_site(href, base_netloc)
        )
    result.contact = contact

    # -- tech signals + summary ------------------------------------------
    combined_text = "\n".join(t for t in (home.text, careers_text, about_text) if t)
    script_srcs = list(home.script_srcs)
    result.tech_signals = parse_tech_signals(combined_text, script_srcs)
    result.summary = summarize(home.text or about_text)

    # -- receipt screenshot -----------------------------------------------
    shot_name = f"{tag}.png"
    shot_path = os.path.join(config.screenshots_dir, shot_name)
    try:
        result.screenshot_path = browser.screenshot(home.url, tag, shot_path) or ""
    except Exception:
        result.screenshot_path = ""

    # -- outreach ----------------------------------------------------------
    draft = draft_outreach(
        company=row.company,
        careers_url=result.careers_url or None,
        tech_signals=result.tech_signals,
        summary=result.summary,
        contact=result.contact or None,
    )
    if config.llm_polish:
        from lead_engine.outreach import polish_with_llm

        context = f"company={row.company} careers={result.careers_url} contact={result.contact}"
        draft = polish_with_llm(draft, context)
    result.outreach_draft = draft

    if not (result.careers_url or result.contact or result.tech_signals or result.summary):
        result.status = "failed"
        result.reason = "no verifiable data extracted from public pages"
    else:
        result.status = "enriched"
    return result


def enrich_companies(
    rows: list[InputRow],
    browser: BrowserAdapter,
    config: EngineConfig,
) -> tuple[list[CompanyResult], RunReport]:
    """Enrich every row; one company's failure never stops the run."""
    report = RunReport()
    results: list[CompanyResult] = []
    work = rows[: config.limit] if config.limit and config.limit > 0 else rows
    started = time.time()
    for row in work:
        outcome = enrich_one(row, browser, config)
        results.append(outcome)
        report.processed += 1
        if outcome.status == "enriched":
            report.enriched += 1
        elif outcome.status == "blocked":
            report.blocked += 1
            report.reasons.append(f"{row.company}: blocked — {outcome.reason}")
        else:
            report.failed += 1
            report.reasons.append(f"{row.company}: failed — {outcome.reason}")
    report.reasons.append(f"run wall time: {time.time() - started:.1f}s")
    return results, report
