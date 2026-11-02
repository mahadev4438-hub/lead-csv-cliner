"""Command-line interface; errors go to stderr with a nonzero exit status."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import CleanerError, clean_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lead-csv-cleaner",
        description="Check CSV leads offline and separate clean, review and duplicate rows.",
        epilog="Checks email format only. It does not verify mailboxes or send messages.",
    )
    parser.add_argument("input", type=Path, help="UTF-8 CSV file to check")
    parser.add_argument("-o", "--output-dir", type=Path, help="new report directory (default: INPUT_cleaned)")
    parser.add_argument("--delimiter", choices=("auto", "comma", "semicolon", "tab"), default="auto")
    parser.add_argument("--company-column", help="exact company header if automatic matching is unsuitable")
    parser.add_argument("--email-column", help="exact email header if automatic matching is unsuitable")
    parser.add_argument("--require", action="append", default=[], metavar="COLUMN", help="extra required column; repeat for multiple columns")
    parser.add_argument("--fail-on-issues", action="store_true", help="exit 1 after writing reports if review or duplicate rows exist")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    destination = args.output_dir or args.input.with_name(args.input.stem + "_cleaned")
    try:
        summary = clean_csv(
            args.input, destination,
            delimiter=args.delimiter, company_column=args.company_column,
            email_column=args.email_column, required_columns=args.require,
        )
    except (CleanerError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(
        f"Checked {summary['total_rows']} leads | Clean: {summary['clean_rows']} | "
        f"Review: {summary['review_rows']} | Duplicates: {summary['duplicate_rows']}"
    )
    print(f"Reports: {destination.resolve()}")
    print("Email format checked only; mailbox delivery is not verified.")
    return int(args.fail_on_issues and bool(summary["review_rows"] + summary["duplicate_rows"]))
