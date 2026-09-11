"""URL classification: careers / about / contact page detection.

Only the URL path (plus query) is considered — never page content — so these
helpers are pure, fast, and unit-testable. Matching is segment-based to avoid
false positives such as ``/about-jobs-fair`` matching careers.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_SPLIT_RE = re.compile(r"[/_?#=&.]+")

def _norm(seg: str) -> str:
    """Normalize one segment: lowercase, drop hyphens, singularize basics."""
    s = seg.lower().replace("-", "")
    if s.endswith("ies") and len(s) > 4:
        s = s[:-3] + "y"
    elif s.endswith("s") and len(s) > 4 and not s.endswith("ss"):
        s = s[:-1]
    return s

# Canonical keyword sets, stored normalized (hyphenless, singular).
CAREERS_KEYWORDS = frozenset(
    {_norm(k) for k in
     ("career", "careers", "job", "jobs", "hiring", "join-us", "join-our-team",
      "work-with-us", "opportunities", "vacancies", "vacancy", "talent")}
)
ABOUT_KEYWORDS = frozenset(
    {_norm(k) for k in
     ("about", "about-us", "company", "who-we-are", "our-story", "our-team",
      "team", "mission", "story")}
)
CONTACT_KEYWORDS = frozenset(
    {_norm(k) for k in
     ("contact", "contacts", "contact-us", "get-in-touch", "support", "help",
      "hello", "reach-us")}
)


def _segments(url: str) -> list[str]:
    """Normalized path+query segments (hyphenless, singular)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return []
    haystack = (parsed.path or "") + "?" + (parsed.query or "")
    return [_norm(seg) for seg in _SPLIT_RE.split(haystack) if seg]


def _matches(url: str, keywords: frozenset[str]) -> bool:
    return any(seg in keywords for seg in _segments(url))


def is_careers_url(url: str) -> bool:
    """True if the URL path looks like a hiring/careers page."""
    return _matches(url, CAREERS_KEYWORDS)


def is_about_url(url: str) -> bool:
    """True if the URL path looks like an about/company page."""
    return _matches(url, ABOUT_KEYWORDS)


def is_contact_url(url: str) -> bool:
    """True if the URL path looks like a contact page."""
    return _matches(url, CONTACT_KEYWORDS)


def same_site(url: str, base_netloc: str) -> bool:
    """True for absolute http(s) URLs on the same host:port as the source page."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and parsed.netloc.lower() == base_netloc.lower()


def pick_link(
    links: list[tuple[str, str]], predicate, base_netloc: str
) -> str | None:
    """Pick the best same-site link matching *predicate*.

    ``links`` are ``(href, text)`` pairs. Preference order: shortest path
    first (``/careers`` beats ``/company/about/careers-and-culture``), with
    links whose *visible text* also mentions the topic ranked first.
    Returns the href or None.
    """
    candidates = [
        href for href, _text in links
        if predicate(href) and same_site(href, base_netloc)
    ]
    if not candidates:
        return None

    def rank(href: str) -> tuple[int, int]:
        parsed = urlparse(href)
        text_hit = 0
        for _h, text in links:
            if _h == href and predicate("x://host/" + text.lower().replace(" ", "-")):
                text_hit = 1
                break
        return (0 if text_hit else 1, len(parsed.path.rstrip("/") or "/"))

    return sorted(candidates, key=rank)[0]


def pick_careers_link(
    links: list[tuple[str, str]], base_netloc: str
) -> str | None:
    """Best same-site careers-page candidate, or None."""
    return pick_link(links, is_careers_url, base_netloc)


def pick_about_link(
    links: list[tuple[str, str]], base_netloc: str
) -> str | None:
    """Best same-site about-page candidate, or None."""
    return pick_link(links, is_about_url, base_netloc)


def pick_contact_link(
    links: list[tuple[str, str]], base_netloc: str
) -> str | None:
    """Best same-site contact-page candidate, or None."""
    return pick_link(links, is_contact_url, base_netloc)
