# TESTING — hermes-lead-engine

## Works without credentials

Everything below runs fully offline — no network beyond localhost, no API
keys, no accounts:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m playwright install chromium   # first time only
.venv/bin/python -m pytest -q                     # 29 tests, ~10s
bash scripts/demo.sh                              # 3-company offline demo
```

What the suite covers:

- Unit: CSV validation (good rows, missing columns, malformed rows with
  line numbers, blank-line handling), URL classification (careers / about /
  contact detection, no substring false positives, shortest-path picking,
  cross-site rejection), tech-signal parsing (framework/language/cloud/
  platform hits, `signal` wording, `java`-vs-`javascript` style traps),
  outreach drafts (two sentences, verified-facts-only, polish is a no-op
  without a key), xlsx writer round-trip, email/summary helpers,
  fail-one-site-continues-others via `FakeAdapter`.
- E2E offline (`tests/test_e2e_offline.py`): real headless Chromium against
  the synthetic fixture site on `127.0.0.1:8611` — Acme Robotics enriches
  with careers URL + about URL + contact + tech signals + summary +
  screenshot receipt on disk; Brightline Studio keeps an EMPTY careers
  field (never guessed); Captcha Corp blocks cleanly with a logged reason;
  a mixed 3-row run reports `enriched=2, blocked=1`.

Verified on this build machine (real runs, not estimates): `pytest -q`
prints `29 passed`; `scripts/demo.sh` prints
`processed=3 enriched=2 failed=0 blocked=1 skipped=0` and writes
`out/enriched-demo.xlsx` plus two real PNG screenshots (magic bytes
`89 50 4E 47` confirmed on disk).

## Needs credentials (live testing only)

| Credential | Where to get it | Where it goes | What it unlocks |
|---|---|---|---|
| (none) | — | — | Public-site enrichment runs need NO credentials — that is the point. |
| `LEAD_ENGINE_LLM_API_KEY` (optional) | OpenAI dashboard → API keys (or any OpenAI-compatible provider) → create key | `.env` file (copied from `.env.example`) or exported in the shell; never committed | `--llm-polish`: rephrases each outreach draft via the chat endpoint. Without it, drafts use the built-in template. |

Optional endpoint overrides (same "where it goes" as above):
`LEAD_ENGINE_LLM_ENDPOINT` (default
`https://api.openai.com/v1/chat/completions`),
`LEAD_ENGINE_LLM_MODEL` (default `gpt-4o-mini`).

## Live test, step by step (Mahmoud's checklist)

1. Prepare a live CSV, e.g. `live.csv`:
   `company,domain` + one real row, e.g. `Example Inc,example.com`.
2. Dry-run headless, one row:
   `.venv/bin/enrich --input live.csv --output live.xlsx --limit 1`
3. Inspect `live.xlsx` (`leads` + `run_report` sheets) and the PNG in
   `screenshots/`.
4. Headed run (desktop only, watch the browser):
   `.venv/bin/enrich --input live.csv --output live.xlsx --headed --limit 1`
5. LLM polish (needs the key from the table above):
   `export LEAD_ENGINE_LLM_API_KEY=...`
   `.venv/bin/enrich --input live.csv --output live.xlsx --llm-polish --limit 1`
   On any API/transport error the template draft is kept — polish never
   breaks a run.

## Behave-well notes (rate limits, walls, scope)

- Pace: jittered human-like pauses between page loads, at most
  `--max-pages` (default 6) public pages per company.
- CAPTCHA / login wall: the row aborts cleanly with status `blocked` and a
  logged reason. Never attempt bypasses; never touch auth-walled pages.
- Scope: homepage → careers → about (+ contact page if one is linked).
  Same-site links only; no form submissions, no downloads.
- Contacts: published emails / contact-page URLs only — never guessed.
  Unverified fields stay EMPTY in the spreadsheet.

## Troubleshooting

- `playwright install chromium` fixes "Executable doesn't exist" browser
  launch errors.
- Port clash on 8607/8611: `FIXTURE_PORT=8608 bash scripts/demo.sh`
  (any free port in 8600–8619).
- `enrich` exit code 1 with `blocked=`/`failed=` rows is a completed run
  with per-row outcomes — not a crash. Exit 2 means a CLI/CSV usage error.
