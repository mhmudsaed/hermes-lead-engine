"""Tech-stack signal detection (conservative: "signal", never certainty).

Patterns run over visible page text plus ``<script src>`` values. Every hit is
reported as e.g. ``React [framework signal]`` — the word *signal* is part of
the output format so downstream readers never mistake it for a confirmed fact.
Patterns use word boundaries / distinctive tokens to avoid false positives
(``java`` must not fire on ``javascript``; ``go`` only fires on ``golang``).
"""
from __future__ import annotations

import re

# name -> (category, [regexes, case-insensitive])
_TECH_PATTERNS: dict[str, tuple[str, list[str]]] = {
    # --- frameworks / libraries ---
    "React": ("framework", [r"react(?:\.js|\.dom)?", r"__REACT", r"react-dom"]),
    "Next.js": ("framework", [r"next\.js", r"__NEXT_DATA__", r"/_next/"]),
    "Vue": ("framework", [r"vue(?:\.js)?(?:\s|$|/|\.)", r"__VUE__", r"/_nuxt/"]),
    "Nuxt": ("framework", [r"nuxt(?:\.js)?", r"/_nuxt/"]),
    "Angular": ("framework", [r"\bangular(?:js|\.js)?\b", r"ng-version"]),
    "Svelte": ("framework", [r"\bsvelte\b", r"sveltekit"]),
    "Gatsby": ("framework", [r"\bgatsby\b"]),
    "jQuery": ("framework", [r"jquery"]),
    "Django": ("framework", [r"\bdjango\b", r"csrfmiddlewaretoken"]),
    "Flask": ("framework", [r"\bflask\b"]),
    "FastAPI": ("framework", [r"fastapi", r"/openapi\.json"]),
    "Ruby on Rails": ("framework", [r"ruby on rails", r"\brails\b(?! trail)", r"authenticity_token"]),
    "Laravel": ("framework", [r"\blaravel\b"]),
    "Express": ("framework", [r"\bexpress(?:\.js)?\b(?! delivery| shipping)", r"x-powered-by.{0,20}express"]),
    "ASP.NET": ("framework", [r"asp\.net", r"__VIEWSTATE", r"\.aspx\b"]),
    "Spring": ("framework", [r"\bspring(?: framework| boot)?\b", r"springframework"]),
    # --- languages ---
    "Python": ("language", [r"\bpython\b", r"\.py\b"]),
    "TypeScript": ("language", [r"typescript", r"\.tsx?\b"]),
    "JavaScript": ("language", [r"\bjavascript\b", r"\becmascript\b", r"\.jsx?\b"]),
    "Go": ("language", [r"\bgolang\b"]),
    "Rust": ("language", [r"\brust\b(?! -)", r"rustc"]),
    "Java": ("language", [r"\bjava\b(?!script)"]),
    "Ruby": ("language", [r"\bruby\b(?! on rails is a gem)"]),
    "PHP": ("language", [r"\bphp\b", r"\.php\b"]),
    "C#/.NET": ("language", [r"c#", r"\.net\b(?!flix)"]),
    "Kotlin": ("language", [r"\bkotlin\b"]),
    "Swift": ("language", [r"\bswift\b(?! logistics| courier)"]),
    # --- cloud / hosting / CDN ---
    "AWS": ("cloud", [r"\baws\b", r"amazon web services", r"cloudfront", r"\.amazonaws\.com"]),
    "Google Cloud": ("cloud", [r"google cloud", r"\bgcp\b", r"googleapis\.com", r"gstatic\.com"]),
    "Azure": ("cloud", [r"\bazure\b", r"microsoft azure", r"\.cloudapp\.", r"\.azurewebsites\."]),
    "Cloudflare": ("cloud", [r"cloudflare", r"__cfduid", r"cf-ray"]),
    "Vercel": ("cloud", [r"\bvercel\b"]),
    "Netlify": ("cloud", [r"\bnetlify\b"]),
    "Heroku": ("cloud", [r"\bheroku(app)?\b"]),
    "DigitalOcean": ("cloud", [r"digitalocean"]),
    "Fastly": ("cloud", [r"\bfastly\b"]),
    # --- CMS / commerce ---
    "WordPress": ("platform", [r"wordpress", r"wp-content", r"wp-includes"]),
    "Shopify": ("platform", [r"shopify", r"myshopify\.com", r"cdn\.shopify\.com"]),
    "Webflow": ("platform", [r"webflow"]),
    "Wix": ("platform", [r"\bwix\b", r"wixstatic\.com"]),
    "Squarespace": ("platform", [r"squarespace", r"static1\.squarespace\.com"]),
    "Drupal": ("platform", [r"\bdrupal\b"]),
    "Ghost": ("platform", [r"\bghost\b(?! writer| kitchen)"]),
}

_COMPILED: dict[str, tuple[str, list[re.Pattern]]] = {
    name: (cat, [re.compile(p, re.IGNORECASE) for p in patterns])
    for name, (cat, patterns) in _TECH_PATTERNS.items()
}


def parse_tech_signals(page_text: str, script_srcs: list[str] | None = None) -> list[str]:
    """Return sorted ``["Name [category signal]", ...]`` hits.

    Both inputs are untrusted page content; they are only regex-scanned,
    never executed or interpreted.
    """
    haystack = page_text or ""
    if script_srcs:
        haystack += "\n" + "\n".join(script_srcs)
    hits: list[str] = []
    for name, (category, patterns) in _COMPILED.items():
        if any(p.search(haystack) for p in patterns):
            hits.append(f"{name} [{category} signal]")
    return sorted(hits)
