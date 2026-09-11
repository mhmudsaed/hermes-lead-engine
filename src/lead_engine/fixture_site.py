"""Synthetic fixture site: tiny local HTTP server with fake company pages.

Used by the offline demo (``scripts/demo.sh``) and the offline browser tests.
All companies, people, emails, and facts below are synthetic — nothing here
describes a real business.

Routes (``<slug>`` = ``acme-robotics`` | ``brightline-studio`` | ``captcha-corp``):

    /<slug>/          homepage (nav links to sub-pages)
    /<slug>/careers   hiring page (absent for brightline-studio)
    /<slug>/about     about page
    /<slug>/contact   contact page (absent for captcha-corp)

Run directly: ``python -m lead_engine.fixture_site --port 8607``.
"""
from __future__ import annotations

import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COMPANIES = {
    "acme-robotics": {
        "name": "Acme Robotics",
        "home_title": "Acme Robotics — Autonomous warehouse robots",
        "home_body": (
            "Acme Robotics builds autonomous warehouse robots that move pallets "
            "without human drivers. Our web app is built with React and our API "
            "is written in Python with Django, all hosted on AWS."
        ),
        "careers_body": (
            "Careers at Acme Robotics. Join our team — open roles in robotics "
            "software and field operations. We are hiring robot operators and "
            "Python engineers in Amman and remotely."
        ),
        "about_body": (
            "About Acme Robotics. Founded in 2021, Acme Robotics is a 40-person "
            "team making warehouses faster with autonomous mobile robots."
        ),
        "contact_email": "hello@acme-robotics.example",
    },
    "brightline-studio": {
        "name": "Brightline Studio",
        "home_title": "Brightline Studio — Brand and web studio",
        "home_body": (
            "Brightline Studio is a small brand and web studio. "
            "This site runs on WordPress and we publish articles about design."
        ),
        "careers_body": None,  # no hiring page on purpose
        "about_body": (
            "About Brightline Studio. We are a five-person studio designing "
            "logos and marketing sites for local shops since 2019."
        ),
        "contact_email": "studio@brightline.example",
    },
    "captcha-corp": {
        "name": "Captcha Corp",
        "home_title": "Captcha Corp — Please verify",
        "home_body": (
            "Please verify you are human before continuing. "
            "This site is protected by reCAPTCHA and you must sign in to "
            "continue browsing company information."
        ),
        "careers_body": None,
        "about_body": None,
        "contact_email": None,
    },
}


def _page(
    title: str,
    heading: str,
    body: str,
    nav: list[tuple[str, str]],
    script_src: str | None = None,
) -> bytes:
    links = " | ".join(
        f'<a href="{href}">{html.escape(text)}</a>' for href, text in nav
    )
    script_tag = (
        f"<script src=\"{html.escape(script_src)}\"></script>"
        if script_src
        else ""
    )
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title></head><body>"
        f"<h1>{html.escape(heading)}</h1>"
        f"<nav>{links}</nav>"
        f"<main><p>{html.escape(body)}</p></main>"
        f"{script_tag}"
        "</body></html>"
    )
    return doc.encode("utf-8")


def render(slug: str, page: str) -> bytes | None:
    """Render a fixture page, or None for unknown slug/page ( -> 404)."""
    company = COMPANIES.get(slug)
    if company is None:
        return None
    name = company["name"]
    base = f"/{slug}"
    if page == "home":
        nav = [(f"{base}/about", "About us")]
        contact_email = company["contact_email"]
        # Per-company <script src> fingerprints so tech-signal extraction has
        # something honest to find on the fixture pages (mirrors the SPEC's
        # "from page text/scripts" wording).
        script_src = {
            "acme-robotics": "/_next/static/chunks/app.js",
            "brightline-studio": "/wp-content/themes/brightline/app.js",
        }.get(slug)
        if slug == "acme-robotics":
            nav = [
                (f"{base}/careers", "Careers — join our team"),
                (f"{base}/about", "About us"),
                (f"{base}/contact", "Contact"),
            ]
        elif slug == "brightline-studio":
            nav = [(f"{base}/about", "About us"), (f"{base}/contact", "Contact")]
        else:  # captcha-corp: no useful nav
            nav = []
        body = company["home_body"]
        if contact_email and slug == "acme-robotics":
            page_html = _page(company["home_title"], name, body, nav,
                              script_src=script_src)
            extra = (
                f"<footer>Write to us at "
                f"<a href=\"mailto:{contact_email}\">{contact_email}</a></footer>"
                "</body></html>"
            )
            return page_html.replace(b"</body></html>", extra.encode("utf-8"))
        return _page(company["home_title"], name, body, nav,
                     script_src=script_src)
    if page == "careers":
        if not company["careers_body"]:
            return None
        return _page(
            f"Careers — {name}", f"Careers at {name}", company["careers_body"],
            [(base, "Home"), (f"{base}/about", "About us")],
        )
    if page == "about":
        if not company["about_body"]:
            return None
        return _page(
            f"About — {name}", f"About {name}", company["about_body"],
            [(base, "Home"), (f"{base}/contact", "Contact")],
        )
    if page == "contact":
        if not company["contact_email"]:
            return None
        email = company["contact_email"]
        body = f"Contact {name}. Write to us at {email} and we reply within two days."
        return _page(
            f"Contact — {name}", f"Contact {name}", body, [(base, "Home")]
        )
    return None


class _Handler(BaseHTTPRequestHandler):
    server_version = "FixtureSite/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        parts = [p for p in path.split("/") if p]
        slug = parts[0] if parts else ""
        page = parts[1] if len(parts) > 1 else "home"
        if len(parts) > 2:
            slug = ""
        body = render(slug, page) if slug else None
        if body is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"fixture: no such page")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(port: int = 8607) -> ThreadingHTTPServer:
    """Start the fixture server in a background thread; returns the server."""
    import threading

    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the synthetic fixture site.")
    parser.add_argument("--port", type=int, default=8607)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    print(f"fixture site serving synthetic companies at http://127.0.0.1:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
