import io
import datetime
import textwrap
import unittest

from datetime import timedelta
from os import path
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from click.testing import CliRunner
from beancount import loader
from beancount.core import data
from beancount.parser import parser
from beangulp import Ingest
from beangulp import extract
from beangulp import similar
from beangulp import tests


class TestExtract(unittest.TestCase):
    def setUp(self):
        self.importer = tests.utils.Importer(None, "Assets:Tests", None)

    def test_extract_from_file_no_entries(self):
        entries = extract.extract_from_file(self.importer, path.abspath("test.csv"), [])
        self.assertEqual(entries, [])

    def test_extract_from_file(self):
        entries, errors, options = parser.parse_string(
            textwrap.dedent("""
            1970-01-03 * "Test"
              Assets:Tests  1.00 USD

            1970-01-01 * "Test"
              Assets:Tests  1.00 USD

            1970-01-02 * "Test"
              Assets:Tests  1.00 USD
            """)
        )

        importer = mock.MagicMock(wraps=self.importer)
        importer.extract.return_value = entries
        entries = extract.extract_from_file(importer, path.abspath("test.csv"), [])
        dates = [entry.date for entry in entries]
        self.assertSequenceEqual(dates, sorted(dates))

    def test_extract_from_file_ensure_sanity(self):
        entries, errors, options = parser.parse_string("""
            1970-01-01 * "Test"
              Assets:Tests  1.00 USD
            """)

        # Break something.
        entries[-1] = entries[-1]._replace(narration=42)
        importer = mock.MagicMock(wraps=self.importer)
        importer.extract.return_value = entries
        with self.assertRaises(AssertionError):
            extract.extract_from_file(importer, path.abspath("test.csv"), [])


class TestDuplicates(unittest.TestCase):
    def _fees(self, count):
        fee = textwrap.dedent("""\
            2026-10-01 * "Bank fee"
              Assets:Bank  -10.00 AUD
              Expenses:BankFees  10.00 AUD

        """)
        entries, errors, _ = parser.parse_string(fee * count)
        self.assertFalse(errors)
        return entries

    def test_many_to_one_default_and_explicit_false(self):
        for kwargs in ({}, {"match_once": False}):
            with self.subTest(kwargs=kwargs):
                target = self._fees(1)[0]._replace(links=frozenset({"source-id"}))
                entries = [e._replace(links=target.links) for e in self._fees(2)]
                extract.mark_duplicate_entries(
                    entries,
                    [target],
                    timedelta(days=2),
                    similar.same_link_comparator(),
                    **kwargs,
                )
                for entry in entries:
                    self.assertIs(entry.meta[extract.DUPLICATE], target)

    def test_match_once_preserves_extra_occurrences(self):
        for existing_count, new_count in ((0, 2), (1, 2), (2, 3), (3, 2)):
            with self.subTest(existing_count=existing_count, new_count=new_count):
                existing, entries = self._fees(existing_count), self._fees(new_count)
                extract.mark_duplicate_entries(
                    entries,
                    existing,
                    timedelta(days=2),
                    similar.heuristic_comparator(),
                    match_once=True,
                )
                targets = [
                    e.meta[extract.DUPLICATE]
                    for e in entries
                    if extract.DUPLICATE in e.meta
                ]
                self.assertEqual(len(targets), min(existing_count, new_count))
                self.assertEqual(len({id(target) for target in targets}), len(targets))
                for entry in entries[len(targets) :]:
                    self.assertNotIn(extract.DUPLICATE, entry.meta)

    def test_match_once_last_available_and_inclusive_window(self):
        lower, equal1, equal2, upper, outside1, outside2 = self._fees(6)
        lower = lower._replace(date=datetime.date(2026, 9, 29))
        upper = upper._replace(date=datetime.date(2026, 10, 3))
        outside1 = outside1._replace(date=datetime.date(2026, 9, 28))
        outside2 = outside2._replace(date=datetime.date(2026, 10, 4))
        existing = [upper, equal1, outside2, lower, equal2, outside1]
        entries = self._fees(5)
        extract.mark_duplicate_entries(
            entries,
            existing,
            timedelta(days=2),
            similar.heuristic_comparator(),
            match_once=True,
        )
        self.assertEqual(existing, [outside1, lower, equal1, equal2, upper, outside2])
        for entry, target in zip(entries, [upper, equal2, equal1, lower]):
            self.assertIs(entry.meta[extract.DUPLICATE], target)
        self.assertNotIn(extract.DUPLICATE, entries[-1].meta)

    def test_match_once_uses_target_identity(self):
        for alias in (False, True):
            with self.subTest(alias=alias):
                target = self._fees(1)[0]
                other = target if alias else target._replace(meta=target.meta.copy())
                self.assertEqual(target, other)
                entries = self._fees(2)
                extract.mark_duplicate_entries(
                    entries,
                    [target, other],
                    timedelta(days=2),
                    similar.heuristic_comparator(),
                    match_once=True,
                )
                self.assertIs(entries[0].meta[extract.DUPLICATE], other)
                if alias:
                    self.assertNotIn(extract.DUPLICATE, entries[1].meta)
                else:
                    self.assertIs(entries[1].meta[extract.DUPLICATE], target)

    def test_match_once_excludes_marked_existing_targets(self):
        for marker in (True, self._fees(1)[0], False, None):
            with self.subTest(marker=marker):
                target = self._fees(1)[0]
                target.meta[extract.DUPLICATE] = marker
                entries = self._fees(1)
                extract.mark_duplicate_entries(
                    entries,
                    [target],
                    timedelta(days=2),
                    similar.heuristic_comparator(),
                    match_once=True,
                )
                if marker:
                    self.assertNotIn(extract.DUPLICATE, entries[0].meta)
                else:
                    self.assertIs(entries[0].meta[extract.DUPLICATE], target)

    def test_match_once_reserves_premarked_targets_and_repeats(self):
        target = self._fees(1)[0]
        entries = self._fees(2)
        entries[1].meta[extract.DUPLICATE] = target
        compare = mock.Mock(return_value=True)
        for _ in range(2):
            extract.mark_duplicate_entries(
                entries,
                [target],
                timedelta(days=2),
                compare,
                match_once=True,
            )
            self.assertNotIn(extract.DUPLICATE, entries[0].meta)
            self.assertIs(entries[1].meta[extract.DUPLICATE], target)
        compare.assert_not_called()

    def test_match_once_replaces_falsy_input_markers(self):
        for marker in (False, None):
            with self.subTest(marker=marker):
                target = self._fees(1)[0]
                entry = self._fees(1)[0]
                entry.meta[extract.DUPLICATE] = marker
                extract.mark_duplicate_entries(
                    [entry],
                    [target],
                    timedelta(days=2),
                    similar.heuristic_comparator(),
                    match_once=True,
                )
                self.assertIs(entry.meta[extract.DUPLICATE], target)

    def test_match_once_rejects_ambiguous_input_markers_before_allocating(self):
        for marker in (True, "duplicate"):
            with self.subTest(marker=marker):
                entries = self._fees(2)
                entries[1].meta[extract.DUPLICATE] = marker
                compare = mock.Mock(return_value=True)
                with self.assertRaisesRegex(ValueError, "directive-valued"):
                    extract.mark_duplicate_entries(
                        entries,
                        self._fees(1),
                        timedelta(days=2),
                        compare,
                        match_once=True,
                    )
                self.assertNotIn(extract.DUPLICATE, entries[0].meta)
                self.assertIs(entries[1].meta[extract.DUPLICATE], marker)
                compare.assert_not_called()

    def test_match_once_generic_and_cross_type_comparators(self):
        balances, errors, _ = parser.parse_string(
            textwrap.dedent("""
            2026-10-01 balance Assets:Bank -10.00 AUD
            2026-10-01 balance Assets:Bank -10.00 AUD
            2026-10-01 balance Assets:Bank -10.00 AUD
        """)
        )
        self.assertFalse(errors)
        target, first, second = balances
        fee = self._fees(1)[0]
        extract.mark_duplicate_entries(
            [fee, first, second],
            [target],
            timedelta(days=2),
            lambda entry, other: isinstance(entry, data.Balance),
            match_once=True,
        )
        self.assertNotIn(extract.DUPLICATE, fee.meta)
        self.assertIs(first.meta[extract.DUPLICATE], target)
        self.assertNotIn(extract.DUPLICATE, second.meta)
        extract.mark_duplicate_entries(
            [fee],
            [target],
            timedelta(days=2),
            lambda entry, other: True,
            match_once=True,
        )
        self.assertIs(fee.meta[extract.DUPLICATE], target)

    def test_match_once_is_greedy_and_scans_forward(self):
        existing = self._fees(2)
        entries = self._fees(2)
        calls = []

        def compare(entry, target):
            calls.append((entry, target))
            return entry is entries[0] or target is existing[1]

        extract.mark_duplicate_entries(
            entries,
            existing,
            timedelta(days=2),
            compare,
            match_once=True,
        )
        self.assertIs(entries[0].meta[extract.DUPLICATE], existing[1])
        self.assertNotIn(extract.DUPLICATE, entries[1].meta)
        self.assertEqual(
            calls,
            [
                (entries[0], existing[0]),
                (entries[0], existing[1]),
                (entries[1], existing[0]),
            ],
        )

    def test_match_once_self_and_new_object_aliases(self):
        entry = self._fees(1)[0]
        extract.mark_duplicate_entries(
            [entry],
            [entry],
            timedelta(days=2),
            lambda left, right: True,
            match_once=True,
        )
        self.assertNotIn(extract.DUPLICATE, entry.meta)
        existing = self._fees(2)
        extract.mark_duplicate_entries(
            [entry, entry],
            existing,
            timedelta(days=2),
            similar.heuristic_comparator(),
            match_once=True,
        )
        self.assertIs(entry.meta[extract.DUPLICATE], existing[1])

    def test_match_once_overlapping_files_preserve_closing_balance(self):
        class OccurrenceImporter(tests.utils.IdentityImporter):
            def deduplicate(self, entries, existing):
                extract.mark_duplicate_entries(
                    entries,
                    existing,
                    timedelta(days=2),
                    self.cmp,
                    match_once=True,
                )

        fee = (
            '2026-10-01 * "Bank fee"\n'
            "  Assets:Bank  -10.00 AUD\n"
            "  Expenses:BankFees  10.00 AUD\n\n"
        )
        journal = (
            "2026-09-30 open Assets:Bank AUD\n2026-09-30 open Expenses:BankFees AUD\n" + fee
        )
        runner = CliRunner()
        with TemporaryDirectory() as directory:
            journal_path = Path(directory) / "journal.beancount"
            first_path = Path(directory) / "a.beans"
            second_path = Path(directory) / "b.beans"
            journal_path.write_text(journal, encoding="utf-8")
            first_path.write_text(fee * 2, encoding="utf-8")
            second_path.write_text(fee * 3, encoding="utf-8")
            ingest = Ingest([OccurrenceImporter(None, "Assets:Bank", "*.beans")])
            result = runner.invoke(
                ingest.cli,
                ["extract", str(first_path), str(second_path), "-e", str(journal_path)],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            output = result.stdout
            self.assertEqual(output.count("; duplicate of "), 3)
            self.assertEqual(output.count("; duplicate of " + str(journal_path) + ":3"), 2)
            self.assertIn("; duplicate of " + str(first_path) + ":5", output)
            self.assertNotIn("; duplicate of " + str(first_path) + ":1", output)
            entries, errors, _ = loader.load_string(
                journal + output + "\n2026-10-02 balance Assets:Bank -30.00 AUD\n"
            )
            self.assertFalse(errors)
            self.assertEqual(len(list(data.filter_txns(entries))), 3)

    def test_mark_duplicate_entries(self):
        entries, error, options = parser.parse_string(
            textwrap.dedent("""
          1970-01-01 * "Test"
            Assets:Tests  10.00 USD

          1970-01-02 * "Test"
            Assets:Tests  20.00 USD
        """)
        )
        compare = similar.heuristic_comparator()
        extract.mark_duplicate_entries(entries, entries[:1], timedelta(days=2), compare)
        self.assertTrue(entries[0].meta[extract.DUPLICATE])
        self.assertNotIn(extract.DUPLICATE, entries[1].meta)


class TestPrint(unittest.TestCase):
    def test_print_extracted_entries(self):
        entries, error, options = parser.parse_string(
            textwrap.dedent("""
            1970-01-01 * "Test"
              Assets:Tests  10.00 USD""")
        )

        extracted = [
            ("/path/to/test.csv", entries, None, None),
            ("/path/to/empty.pdf", [], None, None),
        ]

        output = io.StringIO()
        extract.print_extracted_entries(extracted, output)

        self.assertEqual(
            output.getvalue(),
            textwrap.dedent("""\
            ;; -*- mode: beancount -*-

            **** /path/to/test.csv

            1970-01-01 * "Test"
              Assets:Tests  10.00 USD


            **** /path/to/empty.pdf


            """),
        )

    def test_print_extracted_entries_duplictes(self):
        entries, error, options = parser.parse_string(
            textwrap.dedent("""
            1970-01-01 * "Test"
              Assets:Tests  10.00 USD

            1970-01-01 * "Test"
              Assets:Tests  10.00 USD """)
        )

        # Mark the second entry as duplicate
        entries[1].meta[extract.DUPLICATE] = True

        extracted = [
            ("/path/to/test.csv", entries, None, None),
        ]

        output = io.StringIO()
        extract.print_extracted_entries(extracted, output)

        self.assertEqual(
            output.getvalue(),
            textwrap.dedent("""\
            ;; -*- mode: beancount -*-

            **** /path/to/test.csv

            1970-01-01 * "Test"
              Assets:Tests  10.00 USD

            ; 1970-01-01 * "Test"
            ;   Assets:Tests  10.00 USD


            """),
        )
