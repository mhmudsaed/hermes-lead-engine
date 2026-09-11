"""Browser adapter: Playwright behind a thin interface with an offline fake.

``BrowserAdapter`` is the only seam the enrichment engine touches. Production
uses :class:`PlaywrightAdapter` (real Chromium, one persistent per run with a
fresh incognito-style context per company for cookie/state isolation).
Tests and offline work use :class:`FakeAdapter`, which replays canned page
snapshots with zero network.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PageSnapshot:
    """Everything the engine needs from one loaded page."""

    url: str
    ok: bool
    status: int | None = None
    title: str = ""
    text: str = ""
    script_srcs: list[str] = field(default_factory=list)
    # (absolute href, visible link text)
    links: list[tuple[str, str]] = field(default_factory=list)
    # accessibility-tree-ish node list: (role, name)
    ax_nodes: list[tuple[str, str]] = field(default_factory=list)
    error: str = ""


class BlockedPage(Exception):
    """Raised when a page shows a CAPTCHA / login wall / bot challenge."""


_BLOCK_markers = (
    "captcha", "recaptcha", "hcaptcha", "turnstile",
    "sign in to continue", "log in to continue", "login to continue",
    "verify you are human", "verify you're human", "are you a robot",
    "access denied", "request blocked", "unusual traffic",
)


def blocked_reason(text: str, title: str = "") -> str | None:
    """Return a human reason if page text looks like a wall/challenge."""
    hay = f"{title}\n{text}".lower()
    if any(m in hay for m in ("captcha", "recaptcha", "hcaptcha", "cf-turnstile", "turnstile")):
        return "CAPTCHA/bot challenge detected"
    lowered = hay[:4000]
    for marker in (
        "sign in to continue", "log in to continue", "login to continue",
        "verify you are human", "verify you're human", "are you a robot",
        "access denied", "request has been blocked", "unusual traffic",
    ):
        if marker in lowered:
            return f"access wall detected ({marker!r})"
    return None


class BrowserAdapter(ABC):
    """Minimal browser surface used by the enrichment engine."""

    @abstractmethod
    def visit(self, url: str, site_tag: str) -> PageSnapshot:
        """Load *url* in an isolated context for site *site_tag*."""

    @abstractmethod
    def screenshot(self, url: str, site_tag: str, dest_path: str) -> str:
        """Capture the current page for *url* to *dest_path*; return path or ''."""

    @abstractmethod
    def close(self) -> None:
        """Release all browser resources."""


class PlaywrightAdapter(BrowserAdapter):
    """Real Chromium via Playwright.

    One browser process per run; a **fresh incognito context per site**
    (``site_tag``) so cookies/storage never leak between companies. Contexts
    are cached per tag and torn down on :meth:`close`.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 30000,
        min_delay_s: float = 1.0,
        max_delay_s: float = 3.0,
    ) -> None:
        from playwright.sync_api import sync_playwright  # deferred: needs browser pkg

        self._timeout_ms = timeout_ms
        self._min_delay = min_delay_s
        self._max_delay = max_delay_s
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        self._contexts: dict[str, object] = {}
        self._pages: dict[str, object] = {}

    # -- internals ------------------------------------------------------
    def _page_for(self, site_tag: str):
        import random
        import time

        if site_tag not in self._contexts:
            context = self._browser.new_context(
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                ),
            )
            self._contexts[site_tag] = context
            self._pages[site_tag] = context.new_page()
        else:
            # Jittered human-like pause between page loads in one site.
            span = max(0.0, self._max_delay - self._min_delay)
            time.sleep(self._min_delay + random.uniform(0, span))
        return self._pages[site_tag]

    @staticmethod
    def _snapshot_from_page(page, url: str) -> PageSnapshot:
        title = ""
        text = ""
        try:
            title = page.title() or ""
        except Exception:
            pass
        try:
            body = page.locator("body")
            text = body.inner_text(timeout=5000) if body.count() else ""
        except Exception:
            pass
        text = text[:20000]
        script_srcs: list[str] = []
        try:
            script_srcs = page.eval_on_selector_all(
                "script[src]", "els => els.map(e => e.src)"
            )
        except Exception:
            pass
        links: list[tuple[str, str]] = []
        try:
            raw = page.eval_on_selector_all(
                "a[href]",
                "els => els.slice(0, 300).map(e => [e.href, (e.innerText || '').trim().slice(0, 120)])",
            )
            links = [(href, name) for href, name in raw if href]
        except Exception:
            pass
        ax_nodes: list[tuple[str, str]] = []
        try:
            tree = page.accessibility.snapshot()
            stack = [tree] if tree else []
            while stack and len(ax_nodes) < 400:
                node = stack.pop()
                if not isinstance(node, dict):
                    continue
                role = str(node.get("role", ""))
                name = str(node.get("name", ""))[:120]
                if role and name:
                    ax_nodes.append((role, name))
                stack.extend(node.get("children", []) or [])
        except Exception:
            pass
        return PageSnapshot(
            url=page.url, ok=True, title=title[:300], text=text,
            script_srcs=script_srcs[:200], links=links, ax_nodes=ax_nodes,
        )

    # -- BrowserAdapter API ----------------------------------------------
    def visit(self, url: str, site_tag: str) -> PageSnapshot:
        page = self._page_for(site_tag)
        try:
            response = page.goto(url, wait_until="domcontentloaded",
                                 timeout=self._timeout_ms)
        except Exception as exc:
            return PageSnapshot(url=url, ok=False, error=f"navigation failed: {exc}")
        status = response.status if response else None
        if status is not None and status >= 400:
            return PageSnapshot(url=url, ok=False, status=status,
                                error=f"HTTP {status}")
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        snap = self._snapshot_from_page(page, url)
        snap.status = status
        reason = blocked_reason(snap.text, snap.title)
        if reason:
            raise BlockedPage(f"{reason} at {snap.url}")
        return snap

    def screenshot(self, url: str, site_tag: str, dest_path: str) -> str:
        import os

        page = self._pages.get(site_tag)
        if page is None:
            return ""
        try:
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            page.screenshot(path=dest_path, full_page=False)
            return dest_path
        except Exception:
            return ""

    def close(self) -> None:
        for context in self._contexts.values():
            try:
                context.close()
            except Exception:
                pass
        self._contexts.clear()
        self._pages.clear()
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass


class FakeAdapter(BrowserAdapter):
    """Offline replay adapter for tests: canned snapshots keyed by URL.

    ``pages`` maps URL -> PageSnapshot (or BlockedPage instance / Exception to
    raise). Unlisted URLs return ``ok=False`` snapshots. Screenshots write a
    tiny placeholder file so receipt paths exist on disk.
    """

    def __init__(self, pages: dict[str, PageSnapshot | Exception] | None = None) -> None:
        self.pages: dict[str, PageSnapshot | Exception] = dict(pages or {})
        self.visited: list[tuple[str, str]] = []
        self.closed = False

    def visit(self, url: str, site_tag: str) -> PageSnapshot:
        self.visited.append((url, site_tag))
        canned = self.pages.get(url)
        if isinstance(canned, Exception):
            raise canned
        if isinstance(canned, PageSnapshot):
            return canned
        return PageSnapshot(url=url, ok=False, status=404, error="HTTP 404 (fake)")

    def screenshot(self, url: str, site_tag: str, dest_path: str) -> str:
        import os

        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as handle:
            handle.write(b"FAKE-PNG " + url.encode("utf-8")[:100])
        return dest_path

    def close(self) -> None:
        self.closed = True
