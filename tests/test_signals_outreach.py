"""Unit tests: tech-signal parsing + outreach drafts."""
from __future__ import annotations

from lead_engine.outreach import draft_outreach, polish_with_llm
from lead_engine.tech_signals import parse_tech_signals


def test_detects_frameworks_and_cloud():
    text = "We build with React and Python on AWS. Our site uses Next.js chunks."
    signals = parse_tech_signals(text, ["/_next/static/app.js"])
    assert "React [framework signal]" in signals
    assert "Next.js [framework signal]" in signals
    assert "Python [language signal]" in signals
    assert "AWS [cloud signal]" in signals
    # every entry carries the word "signal"
    assert all("signal" in s for s in signals)


def test_no_false_positives():
    # "java" must not fire on "javascript"; "go" only fires on "golang"
    text = "JavaScript developers writing Go services and PHP templates."
    signals = parse_tech_signals(text)
    names = [s.split(" [")[0] for s in signals]
    assert "Java" not in names
    assert "Go" not in names
    assert "JavaScript [language signal]" in signals
    assert "PHP [language signal]" in signals


def test_empty_page_no_signals():
    assert parse_tech_signals("") == []
    assert parse_tech_signals("We sell handmade soap.") == []


def test_draft_uses_only_verified_facts():
    draft = draft_outreach(
        "Acme",
        careers_url="https://acme.com/careers",
        tech_signals=["React [framework signal]"],
        summary="Acme builds warehouse robots.",
        contact="hi@acme.com",
    )
    assert draft == (
        "Hi Acme team — I noticed your hiring page (https://acme.com/careers) "
        "and public-site signals of React on your public site. "
        "I build browser-automation tooling that turns company websites into "
        "enriched lead sheets — happy to share a two-minute teardown of what "
        "I found, no pitch attached."
    )


def test_draft_careers_only():
    assert draft_outreach("Acme", careers_url="https://acme.com/careers").split(". ")[0] == (
        "Hi Acme team — I noticed your hiring page (https://acme.com/careers) "
        "on your public site"
    )


def test_draft_tech_only():
    first = draft_outreach("Acme", tech_signals=["React [framework signal]"]).split(". ")[0]
    assert first == (
        "Hi Acme team — I noticed public-site signals of React on your public site"
    )


def test_draft_summary_only_no_ellipsis_artifact():
    # Trailing period in the source summary must not stack with "..." -> "....".
    draft = draft_outreach(
        "Acme", summary="Brightline Studio is a small brand and web studio.")
    first = draft.split(". ")[0]
    assert "...." not in draft
    assert first == (
        "Hi Acme team — I noticed what you're building "
        "(Brightline Studio is a small brand and web studio...) on your public site"
    )


def test_draft_long_summary_truncates_cleanly():
    draft = draft_outreach(
        "Acme",
        summary=("Brightline Studio is a small brand and web studio. "
                 "And more text here to push past the truncation limit for sure."),
    )
    assert "...." not in draft
    # 113-char source truncated at a word boundary, no trailing punctuation:
    assert ("(Brightline Studio is a small brand and web studio. "
            "And more text here to push past the truncation limit for...)") in draft


def test_draft_contact_only():
    first = draft_outreach("Acme", contact="hi@acme.com").split(". ")[0]
    assert first == (
        "Hi Acme team — I noticed your published contact hi@acme.com "
        "on your public site"
    )


def test_draft_two_bits_joined_with_and():
    draft = draft_outreach(
        "Acme",
        tech_signals=["React [framework signal]", "Python [language signal]"],
        summary="Acme builds warehouse robots for busy ports.",
    )
    first = draft.split(". ")[0]
    assert first == (
        "Hi Acme team — I noticed public-site signals of React, Python "
        "and what you're building (Acme builds warehouse robots for busy ports...) "
        "on your public site"
    )


def test_draft_without_evidence_stays_honest():
    draft = draft_outreach("Acme")
    assert draft == (
        "Hi Acme team — I was looking through your public site. "
        "I build browser-automation tooling that turns company websites into "
        "enriched lead sheets — happy to share a two-minute teardown of what "
        "I found, no pitch attached."
    )


def test_polish_without_key_returns_draft_unchanged(monkeypatch):
    monkeypatch.delenv("LEAD_ENGINE_LLM_API_KEY", raising=False)
    assert polish_with_llm("Hello world.") == "Hello world."
