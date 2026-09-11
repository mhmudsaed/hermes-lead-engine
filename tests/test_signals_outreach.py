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
    assert "Acme" in draft
    assert "https://acme.com/careers" in draft
    assert "React" in draft
    sentences = [s for s in draft.split(". ") if s.strip()]
    assert len(sentences) == 2  # two-sentence note


def test_draft_without_evidence_stays_honest():
    draft = draft_outreach("Acme")
    assert "Acme" in draft
    assert "hiring" not in draft.lower()


def test_polish_without_key_returns_draft_unchanged(monkeypatch):
    monkeypatch.delenv("LEAD_ENGINE_LLM_API_KEY", raising=False)
    assert polish_with_llm("Hello world.") == "Hello world."
