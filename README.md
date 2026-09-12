# hermes-lead-engine

Batch enrichment tool: give it a CSV of company names/domains; it drives a
real browser through each company's site (homepage, careers, about) and
writes back an enriched spreadsheet — hiring page found, tech-stack signals,
a real contact when one is published, plus a two-sentence outreach draft and
screenshot receipts per row.

Built by: autonomous build agent · Backs:
mahmoudsaeed.com/work/lead-engine-enrichment

## Demo

![Demo — a real offline run](docs/assets/demo.gif)


▶️ The enrichment run — full-quality recording (plays inline):

https://github.com/user-attachments/assets/42fb6535-df9d-494e-870c-d1f868326105
![Browser enrichment — real Chromium visiting company pages](docs/assets/browser.gif)


▶️ The browser session it drives — full-quality recording (plays inline):

https://github.com/user-attachments/assets/9e95dc72-9206-4483-a3cb-d3a66efeb867
One command runs the whole pipeline offline with zero credentials: `./scripts/demo.sh`. The suite is also one command — `pytest -q` → **35 passed** (including real-Chromium end-to-end tests). The GIFs above are real recordings (sped up; each opens with a title card): the first is the enrichment run, the second is the real browser session it drives. Full-quality MP4s: [demo](docs/assets/demo.mp4) · [browser](docs/assets/browser.mp4).

## Why

A raw list of company names tells you nothing about who is worth writing to.
Finding the stack, the hiring page, and a real contact by hand runs to a
couple of minutes per company — hours for a list of fifty. This tool does
the slow reading for you, one isolated browser session per site, and leaves
every field EMPTY rather than guessing when nothing verifiable is published.

Design principles (from the spec):

- Accessibility snapshots instead of raw HTML parsing where practical.
- One browser session per source site; a failure on one company never takes
  down the run.
- Screenshots as receipts — if a number or name looks wrong, the original
  page is one glance away.

## Quickstart (offline demo, no credentials)

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
bash scripts/demo.sh
```

That starts the synthetic fixture site on localhost, enriches
`examples/sample_input.csv` (3 synthetic companies), writes
`out/enriched-demo.xlsx` plus screenshots under `out/screenshots-demo/`,
and prints the result table. Expected outcome: 2 enriched, 1 blocked
(Captcha Corp sits behind a synthetic bot wall on purpose).

## Install

Requires Python 3.11+ and a Playwright Chromium binary:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m playwright install chromium   # first time only
```

## Usage

```bash
# Live mode: real domains, real browser, headless by default
enrich --input list.csv --output enriched.xlsx

# Options
enrich --input list.csv --output enriched.xlsx --limit 10   # first 10 rows
enrich --input list.csv --output enriched.xlsx --headed     # visible browser
enrich --input list.csv --output enriched.xlsx \
  --screenshots-dir shots/ --max-pages 4
enrich --input list.csv --output enriched.xlsx --llm-polish # LLM rephrase
                                                            # (needs API key)
```

Input CSV columns: `company`, `domain` (required), `notes` (optional).
Malformed rows are skipped with a reason on stderr and listed on the
`run_report` sheet — the run itself still completes.

Output `.xlsx` sheets:

- `leads`: one row per company — status, homepage/careers/about URLs,
  published contact, tech signals, summary, outreach draft, screenshot path,
  source URLs, reason/notes.
- `run_report`: processed / enriched / failed / blocked / skipped counts
  plus per-row reasons.

### Statuses

- `enriched` — at least one verifiable finding; empty columns mean "not
  published", never "unknown, so guessed".
- `blocked` — CAPTCHA / login wall met; row aborted cleanly with a reason.
- `failed` — homepage unreachable or nothing verifiable extracted.
- input rows that fail validation never reach the browser; they count as
  `skipped` with line number + reason.

## Configuration

| Flag / env | Default | Meaning |
|---|---|---|
| `--input` | (required) | Input CSV path |
| `--output` | (required) | Output `.xlsx` path |
| `--limit` | `0` (all) | Max companies to enrich |
| `--headed` | headless | Run the browser visibly |
| `--screenshots-dir` | `screenshots` | Receipt screenshot directory |
| `--base-url-template` | (empty = live) | Expand input domains via `{slug}`/`{domain}` (fixture/demo use) |
| `--max-pages` | `6` | Max pages fetched per company |
| `--llm-polish` | off | Rephrase drafts via LLM endpoint |
| `LEAD_ENGINE_LLM_API_KEY` | (empty = off) | API key enabling `--llm-polish` |
| `LEAD_ENGINE_LLM_ENDPOINT` | OpenAI chat completions | OpenAI-compatible chat endpoint |
| `LEAD_ENGINE_LLM_MODEL` | `gpt-4o-mini` | Model for polish |
| `FIXTURE_PORT` | `8607` | Fixture/demo localhost port (8600–8619 range) |

## Architecture

```text
list.csv -> csv_input (validate) -> enrich engine -> enriched.xlsx
                                        |
                                  browser adapter seam
                                  /                \
                 PlaywrightAdapter (real Chromium,   FakeAdapter (canned
                 fresh context per company)          snapshots, tests)
                                        |
                    url_rules + tech_signals + outreach
                    (pure helpers: careers/about/contact
                     classification, conservative signal
                     regexes, template drafts)
```

Key files: `src/lead_engine/csv_input.py`, `browser.py`, `enrich.py`,
`url_rules.py`, `tech_signals.py`, `outreach.py`, `xlsx_writer.py`,
`cli.py`, `fixture_site.py`. Tests under `tests/`.

## Live-mode setup (public sites)

No credentials required for public-site runs — that is the point. Optional:
`LEAD_ENGINE_LLM_API_KEY` for `--llm-polish`. Headed vs headless: default
headless works everywhere; pass `--headed` on a desktop to watch the run.
Behave well: the engine rate-limits with jittered human-like pauses, visits
at most `--max-pages` public pages per company, stops (clean row abort, no
bypass attempts) at CAPTCHAs or login walls, and only records published
contacts — never guessed emails. Full detail: `docs/TESTING.md`.
