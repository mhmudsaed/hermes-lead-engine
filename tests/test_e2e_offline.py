"""Offline end-to-end: real Chromium vs the synthetic fixture site (localhost).

Covers the full pipeline — HTTP server -> Playwright browser -> engine ->
assertions on enriched columns + screenshot receipts. No external network:
everything stays on 127.0.0.1. If no browser executable is available the
test fails loudly (per SPEC the browser is required; only a truly missing
binary skips, and the demo states it).
"""
from __future__ import annotations

import shutil

import pytest

from lead_engine.browser import PlaywrightAdapter
from lead_engine.csv_input import InputRow
from lead_engine.enrich import EngineConfig, enrich_companies
from lead_engine.fixture_site import run as run_fixture_site

pytestmark = pytest.mark.e2e

BROWSER_OK = shutil.which("chrome") is not None  # refined below at runtime


@pytest.fixture(scope="module")
def fixture_base_url():
    server = run_fixture_site(port=8611)
    try:
        yield "http://127.0.0.1:8611"
    finally:
        server.shutdown()


@pytest.fixture(scope="module")
def browser():
    try:
        adapter = PlaywrightAdapter(headless=True, min_delay_s=0.0, max_delay_s=0.0)
    except Exception as exc:  # browser truly unavailable
        pytest.skip(f"no browser executable available: {exc}")
    try:
        yield adapter
    finally:
        adapter.close()


def test_e2e_acme_enriched(browser, fixture_base_url, tmp_path):
    config = EngineConfig(
        base_url_template=fixture_base_url + "/{slug}/",
        screenshots_dir=str(tmp_path / "shots"),
    )
    rows = [InputRow(2, "Acme Robotics", "acme-robotics")]
    results, report = enrich_companies(rows, browser, config)
    assert report.enriched == 1, report.reasons
    row = results[0]
    assert row.status == "enriched"
    assert row.careers_url == f"{fixture_base_url}/acme-robotics/careers"
    assert row.about_url == f"{fixture_base_url}/acme-robotics/about"
    assert row.contact == "hello@acme-robotics.example"
    assert "React [framework signal]" in row.tech_signals
    assert "Python [language signal]" in row.tech_signals
    assert "Django [framework signal]" in row.tech_signals
    assert "warehouse robots" in row.summary.lower()
    assert "Acme Robotics" in row.outreach_draft
    assert row.screenshot_path and row.screenshot_path.endswith("acme-robotics.png")
    import os
    assert os.path.exists(row.screenshot_path)
    assert row.homepage_url == f"{fixture_base_url}/acme-robotics/"


def test_e2e_no_careers_page_stays_empty_not_guessed(browser, fixture_base_url, tmp_path):
    config = EngineConfig(
        base_url_template=fixture_base_url + "/{slug}/",
        screenshots_dir=str(tmp_path / "shots2"),
    )
    rows = [InputRow(3, "Brightline Studio", "brightline-studio")]
    (row,), _ = enrich_companies(rows, browser, config)
    assert row.status == "enriched"  # contact + signals + summary still found
    assert row.careers_url == ""  # no hiring page published -> EMPTY, not guessed
    assert row.contact == "studio@brightline.example"
    assert "WordPress [platform signal]" in row.tech_signals


def test_e2e_bot_wall_row_blocked_cleanly(browser, fixture_base_url, tmp_path):
    config = EngineConfig(
        base_url_template=fixture_base_url + "/{slug}/",
        screenshots_dir=str(tmp_path / "shots3"),
    )
    rows = [InputRow(4, "Captcha Corp", "captcha-corp")]
    results, report = enrich_companies(rows, browser, config)
    assert report.blocked == 1, report.reasons
    assert results[0].status == "blocked"
    assert "challenge" in results[0].reason.lower() or "wall" in results[0].reason.lower()


def test_e2e_mixed_run_continues_past_failure(browser, fixture_base_url, tmp_path):
    config = EngineConfig(
        base_url_template=fixture_base_url + "/{slug}/",
        screenshots_dir=str(tmp_path / "shots4"),
    )
    rows = [
        InputRow(2, "Acme Robotics", "acme-robotics"),
        InputRow(3, "Captcha Corp", "captcha-corp"),
        InputRow(4, "Brightline Studio", "brightline-studio"),
    ]
    results, report = enrich_companies(rows, browser, config)
    assert report.processed == 3
    assert report.enriched == 2 and report.blocked == 1
    assert [r.status for r in results] == ["enriched", "blocked", "enriched"]
