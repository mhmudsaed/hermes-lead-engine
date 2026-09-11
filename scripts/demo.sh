#!/usr/bin/env bash
# Offline demo: enrich the 3-company sample CSV against the synthetic
# fixture site (localhost only, no network, no credentials) and print the
# result table from the generated .xlsx.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

PORT="${FIXTURE_PORT:-8607}"
BASE_URL="http://127.0.0.1:${PORT}"
OUT="${1:-out/enriched-demo.xlsx}"
SHOTS="out/screenshots-demo"

if [ ! -x .venv/bin/python ]; then
  echo "error: .venv missing — create it first (see README install step)" >&2
  exit 2
fi

# 1. Start the synthetic fixture site in the background.
.venv/bin/python -m lead_engine.fixture_site --port "$PORT" >/dev/null 2>&1 &
FIXTURE_PID=$!
trap 'kill $FIXTURE_PID 2>/dev/null || true' EXIT
sleep 1

# 2. Run the enrichment against the fixture site.
#    NOTE: exit code 1 from enrich only means some rows failed/blocked
#    (Captcha Corp is *supposed* to block) — that is the demo working.
set +e
.venv/bin/python -m lead_engine.cli \
  --input examples/sample_input.csv \
  --output "$OUT" \
  --screenshots-dir "$SHOTS" \
  --base-url-template "${BASE_URL}/{slug}/"
ENRICH_EXIT=$?
set -e
if [ "$ENRICH_EXIT" -ne 0 ] && [ "$ENRICH_EXIT" -ne 1 ]; then
  echo "error: enrich failed with exit $ENRICH_EXIT" >&2
  exit "$ENRICH_EXIT"
fi

# 3. Show the result table.
.venv/bin/python - "$OUT" <<'EOF'
import sys
from openpyxl import load_workbook
book = load_workbook(sys.argv[1], read_only=True)
leads = book["leads"]
rows = list(leads.iter_rows(values_only=True))
header, data = rows[0], rows[1:]
print(f"\nEnriched {len(data)} companies -> {sys.argv[1]}")
print("-" * 100)
for r in data:
    d = dict(zip(header, r))
    print(f"{d['Company']} [{d['Status']}]")
    print(f"  careers : {d['Careers URL'] or '(none published)'}")
    print(f"  contact : {d['Contact (published only)'] or '(none published)'}")
    print(f"  tech    : {d['Tech signals'] or '(none)'}")
    print(f"  summary : {(d['Summary'] or '')[:90]}")
    print(f"  shot    : {d['Screenshot'] or '(none)'}")
print("-" * 100)
report = {r[0]: r[1] for r in book["run_report"].iter_rows(values_only=True)}
print("run_report:", {k: v for k, v in report.items()
      if k in ("processed", "enriched", "failed", "blocked", "skipped")})
EOF

echo "demo done: $OUT"
