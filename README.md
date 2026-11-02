# Lead CSV Cleaner

An offline Python utility that separates lead lists into **clean rows**, **rows
that need review**, and **duplicate emails**. Useful before importing a CSV into
a CRM, spreadsheet, or lead-research workflow.

**Early version: 0.1.0 · Python 3.10+ · MIT license · No runtime dependencies**

This checks email **format**, not whether a mailbox exists or accepts mail.
It cannot fix an “Address not found” bounce or verify that a contact is suitable
for advertising outreach. No emails are sent and no files are uploaded.

## Quick start

Download the repository with **Code → Download ZIP**, extract it, then open a
terminal in the extracted folder. Or clone it:

```bash
git clone https://github.com/mahadev4438-hub/lead-csv-cliner.git
cd lead-csv-cliner
python3 -m lead_csv_cleaner examples/sample_leads.csv --output-dir reports/demo
```

On Windows, use `py -3` instead of `python3`. Python 3.10 or later must be installed.
The repository URL keeps its existing spelling, `cliner`; the program is called
`lead-csv-cleaner`.

Expected sample result:

```text
Checked 10 leads | Clean: 5 | Review: 3 | Duplicates: 2
```

Open the CSV files in `reports/demo`. Choose a **new output directory** for each
run; the tool refuses to overwrite an existing directory.

[Hindi-English getting started guide](docs/QUICKSTART_HI.md)

## What you get

| File | Contents |
| --- | --- |
| `clean_leads.csv` | Complete rows with supported email syntax, one per email |
| `review.csv` | Missing required fields or invalid/unsupported email formats |
| `duplicates.csv` | Later valid rows sharing a case-insensitive email |
| `summary.json` | Counts, selected columns, and processing rules |

Review and duplicate reports add `_source_row`, `_issues`, and `_duplicate_of`.
Row numbers refer to physical lines in the original CSV, with the header on
line 1. For multiline records, the first physical line is used.

Every nonblank input record appears in exactly one report. Duplicate rows are
retained for review, including their original extra columns. Review rows do not
prevent a later complete row with the same email from being accepted.

## Input and rules

The default required fields are company and email. These headers are recognized
automatically (ignoring case and treating spaces/hyphens as underscores):

| Field | Recognized headers |
| --- | --- |
| Company | `company`, `company_name`, `Company Name` |
| Email | `email`, `business_email`, `email_address`, `Business Email` |

If multiple matching columns exist, choose one explicitly. Any other columns,
such as `country`, `website`, `source_url`, or `lead_key`, are retained.

```bash
# Clean your own file; by default writes next to it in leads_cleaned/
python3 -m lead_csv_cleaner data/leads.csv

# Map other headers and require an additional field
python3 -m lead_csv_cleaner data/leads.csv -o reports/batch-02 --company-column "Business" --email-column "Contact" --require country

# Choose a separator if auto-detection cannot determine it
python3 -m lead_csv_cleaner data/export.csv -o reports/batch-03 --delimiter semicolon

# Exit 1 if review/duplicate rows exist, useful in automated pipelines
python3 -m lead_csv_cleaner data/leads.csv -o reports/batch-04 --fail-on-issues
```

- Reads UTF-8 CSV, including a UTF-8 BOM, quoted commas, and multiline fields.
- Detects comma, semicolon, or tab separators; `--delimiter` overrides detection.
- Requires rectangular rows and unique, nonempty headers. Malformed CSV stops
  processing before reports are written instead of silently dropping fields.
- Trims outer whitespace in exported headers and values. Preserves internal
  whitespace, email casing, unknown fields, and the source file's bytes.
- Groups duplicates by the **whole email, case-insensitively**. It does not remove
  dots, remove `+tags`, merge company names, or deduplicate by website. Rare
  case-sensitive mailboxes and shared addresses should be reviewed manually.
- Leaves missing countries blank. It does not infer country, budget, contact
  ownership, or qualification. All countries are allowed by default.
- Checks common ASCII email syntax. Internationalized local parts, quoted local
  parts, and domain-literal addresses need manual review. Punycode domains are
  accepted when their labels pass the format checks. No DNS or SMTP checks run.
- Exports comma-separated UTF-8 with a BOM for spreadsheet compatibility.
  Formula-like cells (including headers) beginning with `=`, `+`, `-`, or `@`
  receive a leading apostrophe. This changes the exported text intentionally;
  check these cells before reimporting into another system. Spreadsheet software
  differs, so treat untrusted files carefully when editing or resaving them.
- Reads the input into memory. Intended for ordinary lead lists, not files
  larger than available memory. Uses Python's CSV field-size limit.

Reserved report column names cannot be used in the input. Blank records are
skipped and counted. A header-only file produces empty reports. Empty files and
unsupported encodings produce a clear error.

Exit codes: **0** = reports written; **1** = reports written with issues when
`--fail-on-issues` is used; **2** = invalid arguments, input, or output error.

## Optional installation

Running from the downloaded folder requires no package installation. To install
the command in a virtual environment:

```bash
python3 -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install .
lead-csv-cleaner --help
```

Installation may download build tooling. Running the cleaner itself is offline.
The project is not published on PyPI; install from this source folder.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests cover classification, duplicate retention, Unicode and BOM input,
separators, malformed rows, report safety, overwrite protection, and the CLI.
The included GitHub Actions workflow is configured to run tests on Linux, macOS,
and Windows after the files are pushed. Local validation does not establish that
those hosted runs have passed.

The initial implementation was prepared with AI assistance. This is a new
project; no established adoption or long-term maintenance record is claimed.
See [CONTRIBUTING.md](CONTRIBUTING.md) for practical ways to help and
[SECURITY.md](SECURITY.md) for reporting guidance.

All sample organizations, domains, and contacts are fictional. Keep real lead
files in `data/` and reports in `reports/`; both are ignored by Git. Inspect
changes before committing any data.

Licensed under the [MIT License](LICENSE).
