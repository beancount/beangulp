from decimal import Decimal
from os import path
import datetime
import logging
import os
import types
import unittest
from unittest import mock
from shutil import rmtree
from tempfile import mkdtemp

from beangulp import utils


class TestWalk(unittest.TestCase):
    def setUp(self):
        self.temp = mkdtemp()

    def tearDown(self):
        rmtree(self.temp)

    def test_walk_empty(self):
        entries = utils.walk([self.temp])
        self.assertListEqual(list(entries), [])

    def test_walk_simple(self):
        filenames = [path.join(self.temp, name) for name in ('z', 'a', 'b')]
        for filename in filenames:
            with open(filename, 'w'):
                pass

        entries = utils.walk([self.temp])
        self.assertListEqual(list(entries), sorted(filenames))

        entries = utils.walk(filenames)
        self.assertListEqual(list(entries), filenames)

    def test_walk_subdir(self):
        os.mkdir(path.join(self.temp, 'dir'))
        filenames = [path.join(self.temp, 'dir', name) for name in ('a', 'b')]
        for filename in filenames:
            with open(filename, 'w'):
                pass

        entries = utils.walk([self.temp])
        self.assertListEqual(list(entries), filenames)

    def test_walk_mixed(self):
        os.mkdir(path.join(self.temp, 'dir'))
        files = ['c', ('dir', 'a'), ('dir', 'b')]
        filenames = [path.join(self.temp, *p) for p in files]
        for filename in filenames:
            with open(filename, 'w'):
                pass

        entries = utils.walk([self.temp])
        self.assertListEqual(list(entries), filenames)


class TestUtils(unittest.TestCase):

    def test_getmdate(self):
        self.assertIsInstance(utils.getmdate(__file__), datetime.date)

    def test_logger(self):
        logger = utils.logger()
        self.assertIsInstance(logger, types.FunctionType)
        logger = utils.logger(logging.INFO, err=True)
        self.assertIsInstance(logger, types.FunctionType)

    def test_sha1sum(self):
        self.assertRegex(utils.sha1sum(__file__), '[a-f0-9]+')

    def test_is_mimetype(self):
        self.assertTrue(utils.is_mimetype(__file__, {'text/x-python'}))
        self.assertTrue(utils.is_mimetype(__file__, 'text/x-python'))

    def test_search(self):
        self.assertTrue(utils.search_file_regexp(__file__, 'def test_search', encoding='utf8'))
        self.assertFalse(utils.search_file_regexp(__file__, '^$', encoding='utf8'))

    def test_parse_amount(self):
        self.assertEqual(Decimal('-1045.67'), utils.parse_amount('(1,045.67)'))

    def test_validate(self):
        utils.validate_accounts(
            {'cash': 'Cash account', 'position': 'Cash account'},
            {'cash': 'Assets:US:Cash', 'position': 'Assets:Investment'})

        # Missing values.
        with self.assertRaises(ValueError):
            utils.validate_accounts(
                {'cash': 'Cash account', 'position': 'Cash account'},
                {'position': 'Assets:Investment'})

        # Unknown values.
        with self.assertRaises(ValueError):
            utils.validate_accounts(
                {'cash': 'Cash account'},
                {'cash': 'Assets:US:Cash', 'position': 'Assets:Investment'})

        # Invalid values.
        with self.assertRaises(ValueError):
            utils.validate_accounts(
                {'cash': 'Cash account'},
                {'cash': 42})

    def test_idify(self):
        self.assertEqual(
            "A_great_movie_for_us.mp4", utils.idify(" A great movie (for us) .mp4 ")
        )
        self.assertEqual("A____B.pdf", utils.idify("A____B_._pdf"))


class TestDefDictWithKey(unittest.TestCase):
    def test_defdict_with_key(self):
        factory = mock.MagicMock()
        testdict = utils.DefaultDictWithKey(factory)

        testdict["a"]
        testdict["b"]
        self.assertEqual(2, len(factory.mock_calls))
        self.assertEqual(("a",), factory.mock_calls[0][1])
        self.assertEqual(("b",), factory.mock_calls[1][1])
