"""Unit tests: CSV validation."""
from __future__ import annotations

import pytest

from lead_engine.csv_input import load_companies, validate_domain


def _write(tmp_path, text: str) -> str:
    path = tmp_path / "in.csv"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_valid_csv_loads_rows(tmp_path):
    path = _write(tmp_path, "company,domain,notes\nAcme,acme.com,hi\nBeta,https://beta.io,\n")
    rows, errors = load_companies(path)
    assert errors == []
    assert [(r.company, r.domain, r.notes) for r in rows] == [
        ("Acme", "acme.com", "hi"),
        ("Beta", "https://beta.io", ""),
    ]


def test_case_insensitive_headers_and_extra_columns(tmp_path):
    path = _write(
        tmp_path,
        "Company,DOMAIN,Notes,Extra\nAcme,acme.com,n,x\n",
    )
    rows, errors = load_companies(path)
    assert errors == []
    assert len(rows) == 1 and rows[0].company == "Acme"


def test_missing_required_column_raises(tmp_path):
    path = _write(tmp_path, "company,website\nAcme,acme.com\n")
    with pytest.raises(ValueError, match="missing required column"):
        load_companies(path)


def test_empty_file_raises(tmp_path):
    path = _write(tmp_path, "")
    with pytest.raises(ValueError, match="empty"):
        load_companies(path)


def test_malformed_rows_reported_with_line_numbers(tmp_path):
    path = _write(
        tmp_path,
        "company,domain\n"
        ",acme.com\n"          # line 2: missing company
        "Acme,\n"              # line 3: missing domain
        "Bad,bad domain!\n"    # line 4: bad domain
        "\n"                    # blank line ignored
        "Good,good.com\n",     # line 6: fine
    )
    rows, errors = load_companies(path)
    assert [r.company for r in rows] == ["Good"]
    assert [(e.line_no, e.reason) for e in errors] == [
        (2, "missing company name"),
        (3, "missing domain (column 'domain' is required)"),
        (4, "domain contains whitespace: 'bad domain!'"),
    ]


def test_validate_domain_accepts_ports_paths_slugs():
    assert validate_domain("acme.com") is None
    assert validate_domain("https://acme.com/jobs") is None
    assert validate_domain("127.0.0.1:8607/acme-robotics") is None
    assert validate_domain("acme-robotics") is None  # fixture slug
    assert validate_domain("bad domain") is not None
    assert validate_domain("http://-bad-.com") is not None
    assert validate_domain("") is not None
