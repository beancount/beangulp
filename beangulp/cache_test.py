__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import os
import shutil
import tempfile
import time
import unittest

from unittest import mock

from beangulp import cache
from beangulp import file_type
from beangulp import utils


class TestFileMemo(unittest.TestCase):

    def test_cache(self):
        with tempfile.NamedTemporaryFile() as tmpfile:
            shutil.copy(__file__, tmpfile.name)
            wrap = cache._FileMemo(tmpfile.name)

            # Check attributes.
            self.assertEqual(tmpfile.name, wrap.name)

            # Check that caching works.
            converter = mock.MagicMock(return_value='abc')
            self.assertEqual('abc', wrap.convert(converter))
            self.assertEqual('abc', wrap.convert(converter))
            self.assertEqual('abc', wrap.convert(converter))
            self.assertEqual(1, converter.call_count)

    @unittest.skipIf(not file_type.magic, 'python-magic is not installed')
    def test_cache_head_and_contents(self):
        with tempfile.NamedTemporaryFile() as tmpfile:
            shutil.copy(__file__, tmpfile.name)
            wrap = cache._FileMemo(tmpfile.name)

            contents = wrap.convert(cache.contents)
            self.assertIsInstance(contents, str)
            self.assertGreater(len(contents), 128)

            contents2 = wrap.contents()
            self.assertEqual(contents, contents2)

            head = wrap.convert(cache.head(128))
            self.assertIsInstance(head, str)
            self.assertEqual(128, len(head))

            mimetype = wrap.convert(cache.mimetype)
            self.assertRegex(mimetype, r'text/(x-(python|c\+\+)|plain)')

    def test_cache_head_obeys_explict_utf8_encoding_avoids_chardet_exception(self):
        emoji_header = 'asciiHeader1,🍏Header1,asciiHeader2'.encode('utf-8')
        with mock.patch('builtins.open',
                mock.mock_open(read_data=emoji_header)):
            try:
                function_return = cache._FileMemo('anyFile').head(encoding='utf-8')
            except UnicodeDecodeError:
                self.fail("Failed to decode emoji")


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        cache.CACHEDIR = os.path.join(self.tempdir, 'cache')
        os.mkdir(cache.CACHEDIR)
        self.filename = os.path.join(self.tempdir, 'test.txt')
        with open(self.filename, 'w') as f:
            pass

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_no_cache(self):
        counter = 0

        def func(filename):
            nonlocal counter
            counter +=1
            return counter

        r = func(self.filename)
        self.assertEqual(r, 1)

        r = func(self.filename)
        self.assertEqual(r, 2)

    def test_cache(self):
        counter = 0

        @cache.cache
        def func(filename):
            nonlocal counter
            counter +=1
            return counter

        r = func(self.filename)
        self.assertEqual(r, 1)

        r = func(self.filename)
        self.assertEqual(r, 1)

    def test_cache_expire_mtime(self):
        counter = 0

        @cache.cache
        def func(filename):
            nonlocal counter
            counter +=1
            return counter

        r = func(self.filename)
        self.assertEqual(r, 1)

        r = func(self.filename)
        self.assertEqual(r, 1)

        t = time.time() + 2.0
        os.utime(self.filename, (t, t))

        r = func(self.filename)
        self.assertEqual(r, 2)

        r = func(self.filename)
        self.assertEqual(r, 2)

    def test_cache_expire_args(self):
        counter = 0

        @cache.cache
        def func(filename, arg):
            nonlocal counter
            counter +=1
            return counter

        r = func(self.filename, 1)
        self.assertEqual(r, 1)

        r = func(self.filename, 1)
        self.assertEqual(r, 1)

        r = func(self.filename, 2)
        self.assertEqual(r, 2)

    def test_cache_expire_override(self):
        counter = 0

        @cache.cache
        def func(filename):
            nonlocal counter
            counter +=1
            return counter

        r = func(self.filename)
        self.assertEqual(r, 1)

        r = func(self.filename)
        self.assertEqual(r, 1)

        r = func(self.filename, cache=False)
        self.assertEqual(r, 2)

        r = func(self.filename, cache=True)
        self.assertEqual(r, 2)

        t = time.time() + 2.0
        os.utime(self.filename, (t, t))

        r = func(self.filename, cache=True)
        self.assertEqual(r, 2)

    def test_cache_reset_mtime(self):
        counter = 0

        @cache.cache
        def func(filename):
            nonlocal counter
            counter +=1
            return counter

        r = func(self.filename)
        self.assertEqual(r, 1)

        t = os.stat(self.filename).st_mtime_ns
        with open(self.filename, 'w') as f:
            f.write('baz')
        os.utime(self.filename, ns=(t, t))

        r = func(self.filename)
        self.assertEqual(r, 1)

    def test_cache_key_sha1(self):
        counter = 0

        @cache.cache(key=utils.sha1sum)
        def func(filename):
            nonlocal counter
            counter +=1
            return counter

        with open(self.filename, 'w') as f:
            f.write('test')

        r = func(self.filename)
        self.assertEqual(r, 1)

        r = func(self.filename)
        self.assertEqual(r, 1)

        t = time.time() + 2.0
        os.utime(self.filename, (t, t))

        r = func(self.filename)
        self.assertEqual(r, 1)

        t = os.stat(self.filename).st_mtime_ns
        with open(self.filename, 'w') as f:
            f.write('baz')
        os.utime(self.filename, ns=(t, t))

        r = func(self.filename)
        self.assertEqual(r, 2)
