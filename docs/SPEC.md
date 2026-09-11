# SPEC — Lead Engine (hermes-lead-engine)

Owner: Mahmoud Saeed · Built by: autonomous build agent · Backs: mahmoudsaeed.com/work/lead-engine-enrichment

## Mission

A batch enrichment tool: give it a CSV of company names/domains; it drives a real
browser through each company's site (homepage, careers, about) and writes back an
enriched spreadsheet — hiring page found, tech-stack signals, a real contact when one
is published, plus a two-sentence outreach draft and screenshot receipts per row.

## Problem

A raw list of company names tells you nothing about who is worth writing to. Finding
the stack, the hiring page, and a real contact by hand runs to a couple of minutes per
company — hours for a list of fifty.

## Scope (what to build)

1. **Input**: CSV (columns: company, domain [+ optional notes]); validated, with a
   clear error for malformed rows.
2. **Browser enrichment**: for each company, visit homepage → careers page → about
   page (follow safe links only), extract into structured columns:
   - careers/hiring page URL (verified reachable)
   - tech stack signals (from page text/scripts — conservative list: frameworks,
     languages, cloud hints; mark "signal" not "certainty")
   - contact: published email(s)/contact-page URL only — never guessed
   - short company summary line
3. **Accessibility snapshots over raw HTML**: read the page's accessibility tree for
   element labels/links where practical (cleaner + fewer tokens than raw HTML).
4. **One browser session per source site**: isolate cookies/state per site; a failure
   on one company must not take down the run.
5. **Screenshots as receipts**: every enriched row stores the screenshot + source URL
   it was based on (path recorded in the output).
6. **Output**: enriched .xlsx (openpyxl) with all columns + a run report
   (processed / skipped / failed with reasons). Fields without a verified source stay
   EMPTY rather than guessed.
7. **Outreach draft**: a two-sentence note per row drafted from what was found
   (template-based by default; optional LLM polish behind a flag).
8. **CLI**: `enrich --input list.csv --output enriched.xlsx`, plus flags for limits,
   headless/headed, screenshots dir.

## Hard design decisions (carry these through)

- Accessibility snapshots instead of raw HTML parsing where practical.
- One browser session per source site; isolation per company.
- Screenshots as receipts — if a number or name looks wrong, the original page is one
  glance away.

## Security & guardrails

- Stops and asks (clean abort for that row, logged) on CAPTCHA or login walls.
- Rate-limited, jittered browsing — behaves like a slow human reader.
- Fields without a verified source are left empty, not guessed.
- Only public pages; no auth walls, no bypass attempts.

## Stack

Python 3.11+, Playwright (or equivalent CDP browser driver) — note: the build machine
has browser tooling available; tests must not depend on a network, so design a
**fixture-site mode**: a tiny local HTTP server serving synthetic company pages
(shipped in repo) so the full browser pipeline is tested offline against localhost.
Export via openpyxl.

## Testing requirements

- Offline: fixture site + browser run end-to-end on localhost (headless), asserting
  extracted columns and receipts for the synthetic companies.
- Unit tests: CSV validation, URL classification (careers/about detection), tech-signal
  parsing, output xlsx writer, "fail one site, continue others" behavior.
- One-command demo: `scripts/demo.sh` enriches a sample 3-company CSV against the
  fixture site and shows the result table.

## Definition of Done (checklist)

- [ ] `pytest -q` fully green offline (browser tests run headless against the fixture
      site; skip cleanly-documented only if a browser is truly unavailable, but the
      demo must state that).
- [ ] `scripts/demo.sh` works and shows enrichment output.
- [ ] Sample input CSV + synthetic fixture site in repo, all synthetic.
- [ ] README.md + docs/TESTING.md + docs/STATUS.md + .env.example complete.
- [ ] All work committed; git status clean.

## Credentials for live mode (expand into docs/TESTING.md)

- None required for public-site runs (that is the point — document this).
- Optional: LLM API key for outreach-draft polish; documented env var.
- Document how to run headed vs headless on a desktop.
