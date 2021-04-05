import io
import textwrap
import unittest

from os import path
from unittest import mock

from beancount.parser import parser
from beangulp import extract
from beangulp import tests


class TestExtract(unittest.TestCase):

    def setUp(self):
        self.importer = tests.utils.Importer(None, 'Assets:Tests', None)

    def test_extract_from_file_no_entries(self):
        entries = extract.extract_from_file(self.importer, path.abspath('test.csv'), [])
        self.assertEqual(entries, [])

    def test_extract_from_file(self):
        entries, errors, options = parser.parse_string(textwrap.dedent('''
            1970-01-03 * "Test"
              Assets:Tests  1.00 USD

            1970-01-01 * "Test"
              Assets:Tests  1.00 USD

            1970-01-02 * "Test"
              Assets:Tests  1.00 USD
            '''))

        importer = mock.MagicMock(spec=self.importer)
        importer.extract.return_value = entries
        entries = extract.extract_from_file(importer, path.abspath('test.csv'), [])
        dates = [entry.date for entry in entries]
        self.assertSequenceEqual(dates, sorted(dates))

    def test_extract_from_file_ensure_sanity(self):
        entries, errors, options = parser.parse_string('''
            1970-01-01 * "Test"
              Assets:Tests  1.00 USD
            ''')

        # Break something.
        entries[-1] = entries[-1]._replace(narration=42)
        importer = mock.MagicMock(spec=self.importer)
        importer.extract.return_value = entries
        with self.assertRaises(AssertionError):
            extract.extract_from_file(importer, path.abspath('test.csv'), [])


class TestDuplicates(unittest.TestCase):

    def test_find_duplicate_entries(self):
        entries, error, options = parser.parse_string(textwrap.dedent('''
            1970-01-01 * "Test"
              Assets:Tests  10.00 USD'''))
        extracted = [
            ('/path/to/test.csv', entries, None, None),
        ]
        marked = extract.find_duplicate_entries(extracted, entries)
        self.assertTrue(marked[0][1][0].meta[extract.DUPLICATE])


class TestPrint(unittest.TestCase):

    def test_print_extracted_entries(self):
        entries, error, options = parser.parse_string(textwrap.dedent('''
            1970-01-01 * "Test"
              Assets:Tests  10.00 USD'''))

        extracted = [
            ('/path/to/test.csv', entries, None, None),
            ('/path/to/empty.pdf', [], None, None),
        ]

        output = io.StringIO()
        extract.print_extracted_entries(extracted, output)

        self.assertEqual(output.getvalue(), textwrap.dedent('''\
            ;; -*- mode: beancount -*-

            **** /path/to/test.csv

            1970-01-01 * "Test"
              Assets:Tests  10.00 USD


            **** /path/to/empty.pdf


            '''))

    def test_print_extracted_entries_duplictes(self):
        entries, error, options = parser.parse_string(textwrap.dedent('''
            1970-01-01 * "Test"
              Assets:Tests  10.00 USD

            1970-01-01 * "Test"
              Assets:Tests  10.00 USD '''))

        # Mark the second entry as duplicate
        entries[1].meta[extract.DUPLICATE] = True

        extracted = [
            ('/path/to/test.csv', entries, None, None),
        ]

        output = io.StringIO()
        extract.print_extracted_entries(extracted, output)

        self.assertEqual(output.getvalue(), textwrap.dedent('''\
            ;; -*- mode: beancount -*-

            **** /path/to/test.csv

            1970-01-01 * "Test"
              Assets:Tests  10.00 USD

            ; 1970-01-01 * "Test"
            ;   Assets:Tests  10.00 USD


            '''))
