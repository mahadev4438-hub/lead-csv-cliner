import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lead_csv_cleaner.core import CleanerError, clean_csv, valid_email_format

ROOT = Path(__file__).resolve().parents[1]


class EmailFormatTests(unittest.TestCase):
    def test_common_formats(self):
        for email in ("team@example.com", "first.last+ads@example.co.uk", "a@xn--bcher-kva.example"):
            with self.subTest(email=email):
                self.assertTrue(valid_email_format(email))

    def test_invalid_and_unsupported_formats(self):
        for email in (
            "", "hello@@example.com", "hello@example", "hello@-example.com",
            "hello@example-.com", "hello@example..com", ".hello@example.com",
            "hello.@example.com", "he..llo@example.com", "hello world@example.com",
            "hello@example.com\n", "Name <hello@example.com>", "hello@example.123",
            "a" * 65 + "@example.com", "a@" + "b" * 64 + ".com",
            "用户@example.com", '"quoted local"@example.com',
        ):
            with self.subTest(email=email):
                self.assertFalse(valid_email_format(email))


class CleanerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "leads.csv"
        self.out = self.root / "result"

    def write(self, text, encoding="utf-8"):
        self.source.write_text(text, encoding=encoding)

    def report(self, filename):
        with (self.out / filename).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_documented_sample_counts_and_partition(self):
        summary = clean_csv(ROOT / "examples/sample_leads.csv", self.out)
        self.assertEqual((summary["total_rows"], summary["clean_rows"], summary["review_rows"], summary["duplicate_rows"]), (10, 5, 3, 2))
        self.assertEqual(summary["total_rows"], sum(summary[k] for k in ("clean_rows", "review_rows", "duplicate_rows")))
        self.assertEqual(json.loads((self.out / "summary.json").read_text()), summary)
        self.assertEqual(self.report("duplicates.csv")[0]["_duplicate_of"], "2")
        self.assertEqual(self.report("clean_leads.csv")[-1]["notes"], "'=1+1")

    def test_preserves_source_bytes_and_extra_columns(self):
        self.write("company_name,business_email,source_url,country\n Demo , Hello@Example.com , https://example.com/a ,\n")
        before = self.source.read_bytes()
        clean_csv(self.source, self.out)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.report("clean_leads.csv"), [{"company_name": "Demo", "business_email": "Hello@Example.com", "source_url": "https://example.com/a", "country": ""}])

    def test_missing_row_does_not_hide_later_complete_record(self):
        self.write("company,email\n,team@example.com\nDemo,TEAM@example.com\nOther,team@example.com\n")
        summary = clean_csv(self.source, self.out)
        self.assertEqual((summary["clean_rows"], summary["review_rows"], summary["duplicate_rows"]), (1, 1, 1))
        self.assertEqual(self.report("duplicates.csv")[0]["_duplicate_of"], "3")

    def test_invalid_rows_report_all_issues(self):
        self.write("company,email,country\n,no-at-sign,\nOther,,\n")
        summary = clean_csv(self.source, self.out, required_columns=["country"])
        self.assertEqual(summary["review_rows"], 2)
        self.assertEqual(self.report("review.csv")[0]["_issues"], "missing:company; missing:country; invalid_email_format")

    def test_unknown_country_is_allowed_by_default(self):
        self.write("company,email,country\nDemo,a@example.com,\n")
        summary = clean_csv(self.source, self.out)
        self.assertEqual(summary["clean_rows"], 1)
        self.assertEqual(self.report("clean_leads.csv")[0]["country"], "")

    def test_utf8_bom_and_alias_headers(self):
        self.write("Company Name,Business Email\nनमूना,hello@example.com\n", encoding="utf-8-sig")
        summary = clean_csv(self.source, self.out)
        self.assertEqual(summary["clean_rows"], 1)
        self.assertEqual(self.report("clean_leads.csv")[0]["Company Name"], "नमूना")

    def test_semicolon_and_tab_detection(self):
        for separator, label in ((";", "semicolon"), ("\t", "tab")):
            with self.subTest(delimiter=label):
                self.write(f"company{separator}email\nDemo{separator}hello@example.com\n")
                summary = clean_csv(self.source, self.root / label)
                self.assertEqual(summary["input_delimiter"], label)
                self.assertEqual(summary["clean_rows"], 1)

    def test_explicit_delimiter_and_column_mapping(self):
        self.write("Organisation;Contact;Email\nDemo;hello@example.com;other@example.com\n")
        summary = clean_csv(self.source, self.out, delimiter="semicolon", company_column="Organisation", email_column="Contact")
        self.assertEqual(summary["email_column"], "Contact")
        self.assertEqual(summary["clean_rows"], 1)

    def test_ambiguous_aliases_require_mapping(self):
        self.write("company,email,business_email\nDemo,a@example.com,b@example.com\n")
        with self.assertRaisesRegex(CleanerError, "Multiple matching"):
            clean_csv(self.source, self.out)
        self.assertFalse(self.out.exists())
        self.assertEqual(clean_csv(self.source, self.out, email_column="email")["clean_rows"], 1)

    def test_blank_rows_are_skipped_and_counted(self):
        self.write("company,email\n\n,\n  ,  \nDemo,a@example.com\n")
        summary = clean_csv(self.source, self.out, delimiter="comma")
        self.assertEqual(summary["skipped_blank_rows"], 3)
        self.assertEqual(summary["total_rows"], 1)

    def test_multiline_fields_keep_physical_line_numbers(self):
        self.write('company,email,notes\nDemo,a@example.com,"Line one\nLine two"\nOther,A@example.com,note\n')
        clean_csv(self.source, self.out)
        self.assertEqual(self.report("clean_leads.csv")[0]["notes"], "Line one\nLine two")
        duplicate = self.report("duplicates.csv")[0]
        self.assertEqual((duplicate["_source_row"], duplicate["_duplicate_of"]), ("4", "2"))

    def test_duplicate_headers_rejected(self):
        for header in ("company,email,email", "Company Name,company-name,email"):
            with self.subTest(header=header):
                self.write(header + "\nDemo,a@example.com,b@example.com\n")
                with self.assertRaisesRegex(CleanerError, "duplicate or equivalent"):
                    clean_csv(self.source, self.out)

    def test_empty_and_reserved_headers_rejected(self):
        for header in ("company,email,", "company,email,_issues", "company,email,_SOURCE_ROW"):
            with self.subTest(header=header):
                self.write(header + "\nDemo,a@example.com,x\n")
                with self.assertRaises(CleanerError):
                    clean_csv(self.source, self.out)
                self.assertFalse(self.out.exists())

    def test_empty_file_rejected(self):
        for content in ("", "\ufeff", "  \n"):
            with self.subTest(content=content):
                self.write(content)
                with self.assertRaisesRegex(CleanerError, "empty"):
                    clean_csv(self.source, self.out)

    def test_header_only_produces_empty_reports(self):
        self.write("company,email\n")
        summary = clean_csv(self.source, self.out)
        self.assertEqual(summary["total_rows"], 0)
        for name in ("clean_leads.csv", "review.csv", "duplicates.csv"):
            self.assertEqual(self.report(name), [])

    def test_ragged_rows_abort_without_output(self):
        for row in ("Demo,a@example.com,extra", "Demo"):
            with self.subTest(row=row):
                self.write("company,email\n" + row + "\n")
                with self.assertRaisesRegex(CleanerError, "Row 2"):
                    clean_csv(self.source, self.out, delimiter="comma")
                self.assertFalse(self.out.exists())

    def test_bad_quotes_rejected(self):
        self.write('company,email\nDemo,"a@example.com\n')
        with self.assertRaisesRegex(CleanerError, "Invalid CSV"):
            clean_csv(self.source, self.out, delimiter="comma")

    def test_invalid_encoding_rejected(self):
        self.source.write_bytes(b"company,email\n\xff,a@example.com\n")
        with self.assertRaisesRegex(CleanerError, "UTF-8"):
            clean_csv(self.source, self.out)
        self.assertFalse(self.out.exists())

    def test_nul_characters_rejected(self):
        for content in ("company,email\nDe\x00mo,a@example.com\n", "company,email,no\x00te\nDemo,a@example.com,x\n"):
            with self.subTest(content=content):
                self.write(content)
                with self.assertRaisesRegex(CleanerError, "NUL"):
                    clean_csv(self.source, self.out)
                self.assertFalse(self.out.exists())

    def test_existing_directory_and_input_not_overwritten(self):
        self.write("company,email\nDemo,a@example.com\n")
        self.out.mkdir()
        marker = self.out / "keep.txt"
        marker.write_text("keep")
        with self.assertRaisesRegex(CleanerError, "already exists"):
            clean_csv(self.source, self.out)
        self.assertEqual(marker.read_text(), "keep")
        before = self.source.read_bytes()
        with self.assertRaisesRegex(CleanerError, "already exists"):
            clean_csv(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), before)

    def test_custom_required_column_must_exist(self):
        self.write("company,email\nDemo,a@example.com\n")
        with self.assertRaisesRegex(CleanerError, "Required columns"):
            clean_csv(self.source, self.out, required_columns=["country"])
        self.assertFalse(self.out.exists())

    def test_formula_like_values_escaped_in_all_reports(self):
        self.write('company,email,notes\n=1+1,a@example.com,+1\n@SUM(1),bad,-2\nOther,A@example.com,=2+2\n')
        clean_csv(self.source, self.out)
        self.assertEqual(self.report("clean_leads.csv")[0]["company"], "'=1+1")
        self.assertEqual(self.report("clean_leads.csv")[0]["notes"], "'+1")
        self.assertEqual(self.report("review.csv")[0]["notes"], "'-2")
        self.assertEqual(self.report("duplicates.csv")[0]["notes"], "'=2+2")

    def test_formula_like_headers_escaped(self):
        self.write("company,email,=1+1\nDemo,a@example.com,note\n")
        clean_csv(self.source, self.out)
        self.assertIn("'=1+1", self.report("clean_leads.csv")[0])

    def test_failed_report_write_cleans_up_own_files(self):
        self.write("company,email\nDemo,a@example.com\n")
        real_open = Path.open

        def fail_review(path, *args, **kwargs):
            if path.name == "review.csv":
                raise OSError("simulated write failure")
            return real_open(path, *args, **kwargs)

        with patch.object(Path, "open", fail_review):
            with self.assertRaisesRegex(OSError, "simulated"):
                clean_csv(self.source, self.out)
        self.assertFalse(self.out.exists())


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "lead_csv_cleaner", *map(str, args)], cwd=ROOT, capture_output=True, text=True)

    def test_sample_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_cli(ROOT / "examples/sample_leads.csv", "-o", Path(temp) / "report")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Clean: 5 | Review: 3 | Duplicates: 2", result.stdout)

    def test_fail_on_issues_still_writes_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "report"
            result = self.run_cli(ROOT / "examples/sample_leads.csv", "-o", output, "--fail-on-issues")
            self.assertEqual(result.returncode, 1)
            self.assertTrue((output / "summary.json").is_file())

    def test_missing_input_returns_error_without_traceback(self):
        result = self.run_cli(ROOT / "does-not-exist.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("0.1.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
