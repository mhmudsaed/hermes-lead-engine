"""CSV input loading and validation.

Expected columns: ``company``, ``domain`` (plus optional ``notes``).
The ``domain`` value is kept verbatim — in live mode it is a real domain
(``example.com``), in fixture/demo mode it may be a slug or ``host:port/path``
that is expanded through ``--base-url-template``. Validation therefore only
rejects values that cannot be part of any URL, never real-but-unresolvable
domains (those fail per-row at browse time, not at parse time).
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

REQUIRED_COLUMNS = ("company", "domain")
OPTIONAL_COLUMNS = ("notes",)

# A domain token as typed by a human: optional scheme, host-ish chars,
# optional :port, optional /path prefix (fixture mode slugs live here).
_DOMAIN_RE = re.compile(
    r"^(?:https?://)?"          # optional scheme
    r"[A-Za-z0-9]"              # must start alnum
    r"[A-Za-z0-9._\-/]*"        # host chars, dots, path slashes
    r"(?::\d{1,5})?"            # optional :port
    r"(?:/[A-Za-z0-9._\-/]*)?$"  # optional path
)
_MAX_FIELD_LEN = 500


@dataclass
class InputRow:
    """One validated input row."""

    line_no: int
    company: str
    domain: str
    notes: str = ""


@dataclass
class RowError:
    """One rejected input row with a human-readable reason."""

    line_no: int
    reason: str
    raw: dict = field(default_factory=dict)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def validate_domain(domain: str) -> str | None:
    """Return an error string if *domain* is malformed, else None."""
    if not domain:
        return "missing domain (column 'domain' is required)"
    if len(domain) > _MAX_FIELD_LEN:
        return f"domain too long ({len(domain)} chars, max {_MAX_FIELD_LEN})"
    if any(ch.isspace() for ch in domain):
        return f"domain contains whitespace: {domain!r}"
    if not _DOMAIN_RE.match(domain):
        return f"domain has illegal characters: {domain!r}"
    host = re.sub(r"^https?://", "", domain).split("/")[0].split(":")[0]
    if "." not in host and "/" not in domain and ":" not in domain:
        # Single bare token (e.g. "acme-corp") is a fixture-mode slug.
        # Accept it — the base-url-template decides how it resolves.
        pass
    if ".." in host or host.startswith(("-", ".")) or host.endswith(("-", ".")):
        return f"domain host looks malformed: {host!r}"
    return None


def load_companies(path: str) -> tuple[list[InputRow], list[RowError]]:
    """Load and validate a CSV file.

    Returns ``(rows, errors)``. Fully blank lines are ignored. Header names
    are case-insensitive and may carry extra columns (ignored).
    """
    rows: list[InputRow] = []
    errors: list[RowError] = []
    try:
        handle = open(path, newline="", encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"cannot open input CSV {path!r}: {exc}") from exc
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"input CSV {path!r} is empty (no header row)")
        normalized = {name.strip().lower(): name for name in reader.fieldnames if name}
        missing = [col for col in REQUIRED_COLUMNS if col not in normalized]
        if missing:
            raise ValueError(
                f"input CSV {path!r} is missing required column(s): "
                f"{', '.join(missing)} (found: {', '.join(reader.fieldnames)})"
            )
        company_key = normalized["company"]
        domain_key = normalized["domain"]
        notes_key = normalized.get("notes")
        for line_no, record in enumerate(reader, start=2):
            raw = {k: record.get(k, "") for k in reader.fieldnames or []}
            company = _clean(record.get(company_key))
            domain = _clean(record.get(domain_key))
            notes = _clean(record.get(notes_key)) if notes_key else ""
            if not company and not domain and not notes:
                continue  # blank line
            if not company:
                errors.append(RowError(line_no, "missing company name", raw))
                continue
            domain_error = validate_domain(domain)
            if domain_error:
                errors.append(RowError(line_no, domain_error, raw))
                continue
            if len(company) > _MAX_FIELD_LEN:
                errors.append(
                    RowError(line_no, f"company name too long ({len(company)} chars)", raw)
                )
                continue
            rows.append(InputRow(line_no, company, domain, notes))
    return rows, errors
