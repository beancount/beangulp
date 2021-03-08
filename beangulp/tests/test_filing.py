import os
import unittest

from os import path
from unittest import mock

from beangulp import exceptions
from beangulp import file
from beangulp import tests


class TestFilepath(unittest.TestCase):

    def setUp(self):
        self.importer = tests.utils.Importer(None, 'Assets:Tests', None)

    def test_filepath(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.file_name.return_value = 'foo.csv'
        filepath = file.filepath(importer, path.abspath('test.pdf'))
        self.assertEqual(filepath, 'Assets/Tests/1970-01-01.foo.csv')

    def test_filepath_no_filename(self):
        filepath = file.filepath(self.importer, path.abspath('test.pdf'))
        self.assertEqual(filepath, 'Assets/Tests/1970-01-01.test.pdf')

    def test_filepath_no_date(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.file_date.return_value = None
        with mock.patch('os.path.getmtime', return_value=86401):
            filepath = file.filepath(importer, path.abspath('test.pdf'))
        self.assertEqual(filepath, 'Assets/Tests/1970-01-02.test.pdf')

    def test_filepath_sep_in_name(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.file_name.return_value = f'dir{os.sep:}name.pdf'
        with self.assertRaises(exceptions.Error) as ex:
            filepath = file.filepath(importer, path.abspath('test.pdf'))
        self.assertRegex(ex.exception.message, r'contains path separator')

    def test_filepath_date_in_name(self):
        importer = mock.MagicMock(wraps=self.importer)
        importer.file_name.return_value = '1970-01-03.name.pdf'
        with self.assertRaises(exceptions.Error) as ex:
            filepath = file.filepath(importer, path.abspath('test.pdf'))
        self.assertRegex(ex.exception.message, r'contains [\w\s]+ date')
