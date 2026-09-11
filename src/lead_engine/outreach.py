"""Outreach drafts: template-based by default, optional LLM polish behind a flag.

The template only references facts the browser run actually verified
(careers URL, tech signals, published contact). It never invents names,
roles, funding, or any other detail. LLM polish (``--llm-polish``) only
rephrases that draft; on any failure it returns the template unchanged.
"""
from __future__ import annotations

import json
import os
import urllib.request

MAX_TECH_MENTIONED = 3
MAX_SUMMARY_CHARS = 110


def _trim_summary(summary: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """Shorten *summary* for inline quoting without ellipsis artifacts.

    Trailing sentence punctuation is stripped first, so appending "..."
    never produces "....". Returns "" when there is nothing quotable.
    """
    text = " ".join((summary or "").split())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text.rstrip(".!?")
    cut = text[:max_chars].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".!?,;:")


def _evidence_bits(
    careers_url: str | None,
    tech_signals: list[str],
    summary: str,
    contact: str | None,
) -> list[str]:
    """One self-contained noun phrase per verified fact, max two.

    Each bit reads grammatically after "I noticed ..." on its own, so ANY
    combination of bits joins cleanly with " and ". No bit ends with
    punctuation that could collide with the sentence's own period.
    """
    bits: list[str] = []
    if careers_url:
        bits.append(f"your hiring page ({careers_url})")
    if tech_signals:
        names = [sig.split(" [", 1)[0] for sig in tech_signals[:MAX_TECH_MENTIONED]]
        bits.append("public-site signals of " + ", ".join(names))
    trimmed = _trim_summary(summary)
    if trimmed:
        bits.append(f"what you're building ({trimmed}...)")
    if contact:
        bits.append(f"your published contact {contact}")
    return bits[:2]


def draft_outreach(
    company: str,
    careers_url: str | None = None,
    tech_signals: list[str] | None = None,
    summary: str = "",
    contact: str | None = None,
) -> str:
    """Build a two-sentence outreach note from verified findings only."""
    bits = _evidence_bits(careers_url, tech_signals or [], summary or "", contact)
    if bits:
        first = f"Hi {company} team — I noticed {' and '.join(bits)} on your public site."
    else:
        first = f"Hi {company} team — I was looking through your public site."
    second = (
        "I build browser-automation tooling that turns company websites into "
        "enriched lead sheets — happy to share a two-minute teardown of what "
        "I found, no pitch attached."
    )
    return f"{first} {second}"


def polish_with_llm(draft: str, context: str = "") -> str:
    """Optionally rephrase *draft* via an OpenAI-compatible chat endpoint.

    Active only when ``LEAD_ENGINE_LLM_API_KEY`` is set; otherwise returns the
    draft unchanged. Any transport/API error also returns the draft unchanged —
    polish must never break a run. Reads ``LEAD_ENGINE_LLM_ENDPOINT``
    (default: OpenAI chat completions) and ``LEAD_ENGINE_LLM_MODEL``.
    """
    api_key = os.environ.get("LEAD_ENGINE_LLM_API_KEY", "").strip()
    if not api_key or not draft:
        return draft
    endpoint = os.environ.get(
        "LEAD_ENGINE_LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions"
    ).strip()
    model = os.environ.get("LEAD_ENGINE_LLM_MODEL", "gpt-4o-mini").strip()
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Rephrase the user's outreach draft in at most two sentences. "
                    "Keep every factual claim exactly as-is; do not add names, "
                    "roles, numbers, or promises. Plain, human tone."
                ),
            },
            {
                "role": "user",
                "content": f"Draft: {draft}\nContext (do not add new facts): {context}",
            },
        ],
        "max_tokens": 200,
        "temperature": 0.4,
    }
    try:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8"))
        polished = body["choices"][0]["message"]["content"].strip()
        return polished or draft
    except Exception:
        return draft
