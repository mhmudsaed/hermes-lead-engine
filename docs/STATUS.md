# STATUS — hermes-lead-engine (living status, kept current)

## Done

- CSV input validation with clear per-row errors (missing columns raise;
  malformed rows skip with line number + reason).
- Browser enrichment: homepage → careers → about (+ contact page), one
  fresh Playwright browser context per company, per-row isolation
  (one failure never stops the run), jittered human-like pacing.
- Accessibility-tree snapshot captured per page (`ax_nodes` on the
  snapshot; engine navigates via visible links, not raw HTML).
- Tech-signal detection from page text + script srcs, always worded as
  "signal", with substring-trap guards.
- Published-only contacts (mailto → contact page → visible text, junk
  filtered); unverified fields stay EMPTY.
- Template outreach drafts (two sentences, verified facts only) + optional
  LLM polish behind `--llm-polish` / `LEAD_ENGINE_LLM_API_KEY`, failing
  safe back to the template. First sentence built from self-contained noun
  phrases ("I noticed X and Y on your public site") — grammatical for every
  evidence combination; summary quotes strip trailing punctuation before
  "..." (no "...." artifact). Exact-output unit tests per combination.
- `.xlsx` output (`leads` + `run_report` sheets) via openpyxl.
- CLI: `enrich --input --output` plus `--limit/--headed/--screenshots-dir/
  --base-url-template/--max-pages/--llm-polish`.
- Fixture site (3 synthetic companies on localhost) + sample CSV +
  `scripts/demo.sh` one-command offline demo.
- Suite: 35 tests green (`pytest -q` → `35 passed`), incl. 4 real-Chromium
  offline e2e tests and 7 exact-output outreach-template tests. Demo
  verified: `processed=3 enriched=2 failed=0 blocked=1 skipped=0`, real PNG
  receipts on disk.

## Mocked / faked (by design, tests only)

- `FakeAdapter`: canned page snapshots for unit tests (fail-one-continues,
  empty-result, writer round-trip). Production path always uses
  `PlaywrightAdapter` with real Chromium.
- Fixture site companies/emails/facts are synthetic (RFC 2606 `.example`
  addresses); nothing describes a real business.

## Known limitations

- Single-threaded, one company at a time (politeness over speed).
- No JavaScript-rendered-content waiting beyond `networkidle` + DOM read;
  heavy SPAs may yield thin text.
- English-centric heuristics (URL segments, email regex, summary).
- LLM polish needs an OpenAI-compatible endpoint + key; otherwise template.
- `--headed` needs a desktop/display; CI/servers stay headless.

## Next steps (requires live run)

- Live validation against a few real public company sites ("requires live
  run" — no live claims made in this repo or the case study).
- Optional: parallel workers with per-domain politeness caps; screenshot
  thumbnails embedded in the xlsx; richer accessibility-tree link
  following.

## Decisions log

- Outreach template fix (audit): "I came across you're hiring (url)" was
  ungrammatical (clause after "came across") and bare "..." stacking made
  "....". Bits are now noun phrases under "I noticed ... on your public
  site", joined with "and"; summary trimming strips trailing punctuation
  first. Fact-only rule unchanged — only phrasing changed.
- Kept `networkidle` wait short (8s) + DOM fallback so slow pages degrade
  to partial text instead of failing.
- Fixture script fingerprints are per-company (`/_next/...` vs
  `/wp-content/...`) so signal extraction is honestly exercised.
- `enrich` exits 1 when rows fail/block (outcomes, not crash); 2 for usage
  errors. `demo.sh` treats 1 as success (Captcha Corp is *meant* to block).
