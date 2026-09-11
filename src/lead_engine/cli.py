"""CLI: enrich --input list.csv --output enriched.xlsx (+ limits, headed, shots)."""
from __future__ import annotations

import argparse
import os
import sys

from lead_engine import __version__
from lead_engine.browser import PlaywrightAdapter
from lead_engine.csv_input import RowError, load_companies
from lead_engine.enrich import EngineConfig, enrich_companies
from lead_engine.xlsx_writer import write_workbook


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="enrich",
        description=(
            "Enrich a CSV of companies (company,domain[,notes]) into an .xlsx "
            "via a real browser: hiring pages, tech signals, published "
            "contacts, outreach drafts, screenshot receipts."
        ),
    )
    parser.add_argument("--input", required=True, help="input CSV path")
    parser.add_argument("--output", required=True, help="output .xlsx path")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="max companies to enrich (0 = all)",
    )
    parser.add_argument(
        "--headed", action="store_true",
        help="run the browser headed (default: headless)",
    )
    parser.add_argument(
        "--screenshots-dir", default="screenshots",
        help="directory for receipt screenshots (default: screenshots)",
    )
    parser.add_argument(
        "--base-url-template", default="",
        help=("URL template for resolving input domains, with {slug} or "
              "{domain} placeholder (used by the offline fixture demo)"),
    )
    parser.add_argument(
        "--max-pages", type=int, default=6,
        help="max pages fetched per company (default: 6)",
    )
    parser.add_argument(
        "--llm-polish", action="store_true",
        help=("rephrase outreach drafts via an LLM endpoint "
              "(needs LEAD_ENGINE_LLM_API_KEY; template used otherwise)"),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit < 0:
        print("error: --limit must be >= 0", file=sys.stderr)
        return 2
    if args.max_pages < 1:
        print("error: --max-pages must be >= 1", file=sys.stderr)
        return 2
    try:
        rows, errors = load_companies(args.input)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    skipped: list[RowError] = list(errors)
    for err in errors:
        print(f"skip line {err.line_no}: {err.reason}", file=sys.stderr)
    if not rows:
        print("error: no valid company rows to enrich", file=sys.stderr)
        return 2

    config = EngineConfig(
        base_url_template=args.base_url_template,
        screenshots_dir=args.screenshots_dir,
        max_pages_per_company=args.max_pages,
        llm_polish=args.llm_polish,
        limit=args.limit,
    )
    browser = PlaywrightAdapter(headless=not args.headed)
    try:
        results, report = enrich_companies(rows, browser, config)
    finally:
        browser.close()
    report.skipped = len(skipped)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    write_workbook(args.output, results, report, skipped)

    print(f"processed={report.processed} enriched={report.enriched} "
          f"failed={report.failed} blocked={report.blocked} "
          f"skipped={report.skipped}")
    for reason in report.reasons:
        if not reason.startswith("run wall time"):
            print(f"  - {reason}")
    print(f"wrote {args.output}")
    return 0 if report.failed == 0 and report.blocked == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
