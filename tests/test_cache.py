import os
import shutil
import tempfile
import time
import unittest

import beangulp.cache
import beangulp.testing


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        beangulp.cache.CACHEDIR = os.path.join(self.tempdir, 'cache')
        os.mkdir(beangulp.cache.CACHEDIR)
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

        @beangulp.cache.cache
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

        @beangulp.cache.cache
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

        @beangulp.cache.cache
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

        @beangulp.cache.cache
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

        @beangulp.cache.cache
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

        @beangulp.cache.cache(key=beangulp.testing.sha1sum)
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
