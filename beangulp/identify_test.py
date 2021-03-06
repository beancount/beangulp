import unittest

from os import path

from beangulp import exceptions
from beangulp import identify
from beangulp import tests


class TestIdentify(unittest.TestCase):

    def test_identify(self):
        importers = [
            tests.utils.Importer('A', 'Assets:Tests', 'application/pdf'),
            tests.utils.Importer('B', 'Assets:Tests', 'text/csv'),
        ]

        # Pass an absolute path to identify() to make the cache code
        # used internally by the importers happy. This can go away
        # once FileMemo is removed from the importers interface.
        importer = identify.identify(importers, path.abspath('test.txt'))
        self.assertIsNone(importer)

        importer = identify.identify(importers, path.abspath('test.pdf'))
        self.assertEqual(importer.name(), 'A')

        importer = identify.identify(importers, path.abspath('test.csv'))
        self.assertEqual(importer.name(), 'B')

    def test_identify_collision(self):
        importers = [
            tests.utils.Importer('A', 'Assets:Tests', 'text/csv'),
            tests.utils.Importer('B', 'Assets:Tests', 'text/csv'),
        ]

        importer = identify.identify(importers, path.abspath('test.txt'))
        self.assertIsNone(importer)

        with self.assertRaises(exceptions.Error):
            importer = identify.identify(importers, path.abspath('test.csv'))
