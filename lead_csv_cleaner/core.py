"""Read, classify and export leads without network requests or source edits."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from . import __version__

DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t"}
REPORT_COLUMNS = ("_source_row", "_issues", "_duplicate_of")
ALIASES = {
    "company": {"company", "company_name"},
    "email": {"email", "business_email", "email_address"},
}
LOCAL_PART = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*\Z")
DOMAIN_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")
TOP_LABEL = re.compile(r"(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9-]+)\Z")


class CleanerError(ValueError):
    """An actionable input or output problem."""


def valid_email_format(value: str) -> bool:
    """Check common ASCII mailbox syntax, never ownership or deliverability."""
    if not value.isascii() or len(value) > 254 or value.count("@") != 1:
        return False
    local, domain = value.split("@")
    labels = domain.split(".")
    return bool(
        0 < len(local) <= 64
        and LOCAL_PART.fullmatch(local)
        and len(labels) >= 2
        and all(DOMAIN_LABEL.fullmatch(label) for label in labels)
        and TOP_LABEL.fullmatch(labels[-1])
    )


def _header_key(value: str) -> str:
    return re.sub(r"[\s-]+", "_", value.strip().casefold())


def _resolve_column(headers: list[str], kind: str, explicit: str | None) -> str:
    if explicit is not None:
        if explicit not in headers:
            raise CleanerError(f"Column {explicit!r} was not found in the CSV header.")
        return explicit
    candidates = [name for name in headers if _header_key(name) in ALIASES[kind]]
    if len(candidates) != 1:
        reason = "No matching column" if not candidates else "Multiple matching columns"
        raise CleanerError(
            f"{reason} for {kind}. Use --{kind}-column with its exact header name."
        )
    return candidates[0]


def _read_csv(path: Path, delimiter: str) -> tuple[list[str], list[tuple[int, list[str]]], str, int]:
    if delimiter != "auto" and delimiter not in DELIMITERS:
        raise CleanerError("Delimiter must be auto, comma, semicolon or tab.")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        if not sample.strip():
            raise CleanerError("The CSV is empty. Include a header and lead rows.")
        if delimiter == "auto":
            try:
                separator = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
            except csv.Error:
                # A malformed comma-separated row should produce a precise width error.
                separator = ","
        else:
            separator = DELIMITERS[delimiter]
        reader = csv.reader(handle, delimiter=separator, strict=True)
        try:
            headers = [cell.strip() for cell in next(reader)]
            keys = [_header_key(name) for name in headers]
            if not headers or any(not name for name in headers):
                raise CleanerError("The header contains an empty column name.")
            if any("\x00" in name for name in headers):
                raise CleanerError("The header contains unsupported NUL characters.")
            if len(set(keys)) != len(keys):
                raise CleanerError("The header contains duplicate or equivalent column names.")
            if set(keys).intersection(REPORT_COLUMNS):
                raise CleanerError("Input columns cannot use reserved names: " + ", ".join(REPORT_COLUMNS))
            rows = []
            blank_rows = 0
            while True:
                source_row = reader.line_num + 1
                cells = next(reader, None)
                if cells is None:
                    break
                if not any(cell.strip() for cell in cells):
                    blank_rows += 1
                    continue
                if len(cells) != len(headers):
                    raise CleanerError(
                        f"Row {source_row}: expected {len(headers)} columns, got {len(cells)}. "
                        "Check quoting and --delimiter. No reports were written."
                    )
                if any("\x00" in cell for cell in cells):
                    raise CleanerError(f"Row {source_row}: NUL characters are not supported.")
                rows.append((source_row, [cell.strip() for cell in cells]))
        except csv.Error as error:
            raise CleanerError(f"Invalid CSV near physical line {reader.line_num}: {error}") from error
    return headers, rows, separator, blank_rows


def spreadsheet_cell(value: str) -> str:
    """Prefix formula-like text with an apostrophe in exported CSV files."""
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def clean_csv(
    source: str | Path,
    output_dir: str | Path,
    *,
    delimiter: str = "auto",
    company_column: str | None = None,
    email_column: str | None = None,
    required_columns: Iterable[str] = (),
) -> dict:
    """Write four reports into a new directory and return their count summary.

    Missing/invalid rows go to review first. Among remaining rows, the first
    occurrence of each case-insensitive email is kept; later ones are duplicates.
    Every nonblank input record appears in exactly one CSV report.
    """
    source, destination = Path(source), Path(output_dir)
    try:
        headers, records, separator, blank_rows = _read_csv(source, delimiter)
    except UnicodeError as error:
        raise CleanerError("Input must be UTF-8. Re-export it as CSV UTF-8 and try again.") from error
    company = _resolve_column(headers, "company", company_column)
    email = _resolve_column(headers, "email", email_column)
    if company == email:
        raise CleanerError("Company and email must be different columns.")
    required = list(dict.fromkeys([company, email, *required_columns]))
    missing = [name for name in required if name not in headers]
    if missing:
        raise CleanerError("Required columns were not found: " + ", ".join(missing))

    clean, review, duplicates = [], [], []
    seen: dict[str, int] = {}
    issue_counts: Counter[str] = Counter()
    for source_row, cells in records:
        row = dict(zip(headers, cells))
        issues = [f"missing:{name}" for name in required if not row[name]]
        if row[email] and not valid_email_format(row[email]):
            issues.append("invalid_email_format")
        metadata = {"_source_row": str(source_row), "_issues": "", "_duplicate_of": ""}
        if issues:
            issue_counts.update(issues)
            metadata["_issues"] = "; ".join(issues)
            review.append({**row, **metadata})
        elif row[email].casefold() in seen:
            metadata["_issues"] = "duplicate_email"
            metadata["_duplicate_of"] = str(seen[row[email].casefold()])
            duplicates.append({**row, **metadata})
            issue_counts["duplicate_email"] += 1
        else:
            seen[row[email].casefold()] = source_row
            clean.append(row)

    summary = {
        "version": __version__,
        "input_file": source.name,
        "input_delimiter": {",": "comma", ";": "semicolon", "\t": "tab"}[separator],
        "company_column": company,
        "email_column": email,
        "required_columns": required,
        "total_rows": len(records),
        "clean_rows": len(clean),
        "review_rows": len(review),
        "duplicate_rows": len(duplicates),
        "skipped_blank_rows": blank_rows,
        "issues": dict(sorted(issue_counts.items())),
        "email_check": "common_ascii_format_only; deliverability_not_checked",
        "export_policy": "trim_outer_whitespace; prefix_formula_like_cells_with_apostrophe",
    }
    # An exclusive directory creation prevents overwriting previous output or input.
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise CleanerError(f"Output already exists: {destination}. Choose a new --output-dir.") from error

    created: list[Path] = []
    try:
        for filename, fieldnames, data in (
            ("clean_leads.csv", headers, clean),
            ("review.csv", headers + list(REPORT_COLUMNS), review),
            ("duplicates.csv", headers + list(REPORT_COLUMNS), duplicates),
        ):
            path = destination / filename
            with path.open("x", encoding="utf-8-sig", newline="") as handle:
                created.append(path)
                writer = csv.writer(handle)
                writer.writerow([spreadsheet_cell(name) for name in fieldnames])
                writer.writerows(
                    [spreadsheet_cell(row[name]) for name in fieldnames] for row in data
                )
        path = destination / "summary.json"
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            created.append(path)
            json.dump(summary, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except OSError:
        # Remove only files created by this run; leave any unrelated files alone.
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        try:
            destination.rmdir()
        except OSError:
            pass
        raise
    return summary
