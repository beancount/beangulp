import datetime
import os
import unittest

from os import path
from unittest import mock

from beangulp import archive
from beangulp import exceptions
from beangulp import tests


class TestFilepath(unittest.TestCase):
    def setUp(self):
        self.importer = tests.utils.Importer(None, "Assets:Tests", None)

    def test_filepath(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.filename.return_value = "foo.csv"
        filepath = archive.filepath(importer, path.abspath("test.pdf"))
        self.assertEqual(filepath, "Assets/Tests/1970-01-01.foo.csv")

    def test_filepath_no_filename(self):
        filepath = archive.filepath(self.importer, path.abspath("test.pdf"))
        self.assertEqual(filepath, "Assets/Tests/1970-01-01.test.pdf")

    def test_filepath_no_date(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.date.return_value = None
        with mock.patch(
            "beangulp.archive.utils.getmdate",
            return_value=datetime.datetime.fromtimestamp(0, datetime.timezone.utc),
        ):
            filepath = archive.filepath(importer, path.abspath("test.pdf"))
        self.assertEqual(filepath, "Assets/Tests/1970-01-01.test.pdf")

    def test_filepath_sep_in_name(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.filename.return_value = f"dir{os.sep:}name.pdf"
        with self.assertRaises(exceptions.Error) as ex:
            archive.filepath(importer, path.abspath("test.pdf"))
        self.assertRegex(ex.exception.message, r"contains path separator")

    def test_filepath_date_in_name(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.filename.return_value = "1970-01-03.name.pdf"
        with self.assertRaises(exceptions.Error) as ex:
            archive.filepath(importer, path.abspath("test.pdf"))
        self.assertRegex(ex.exception.message, r"contains [\w\s]+ date")
