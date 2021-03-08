import unittest

from os import mkdir, path
from shutil import rmtree
from tempfile import mkdtemp


from beangulp.utils import walk


class TestWalk(unittest.TestCase):
    def setUp(self):
        self.temp = mkdtemp()

    def tearDown(self):
        rmtree(self.temp)

    def test_walk_empty(self):
        entries = walk([self.temp])
        self.assertListEqual(list(entries), [])

    def test_walk_simple(self):
        filenames = [path.join(self.temp, name) for name in ('z', 'a', 'b')]
        for filename in filenames:
            with open(filename, 'w'):
                pass

        entries = walk([self.temp])
        self.assertListEqual(list(entries), list(sorted(filenames)))

        entries = walk(filenames)
        self.assertListEqual(list(entries), filenames)

    def test_walk_subdir(self):
        mkdir(path.join(self.temp, 'dir'))
        filenames = [path.join(self.temp, 'dir', name) for name in ('a', 'b')]
        for filename in filenames:
            with open(filename, 'w'):
                pass

        entries = walk([self.temp])
        self.assertListEqual(list(entries), filenames)

    def test_walk_mixed(self):
        mkdir(path.join(self.temp, 'dir'))
        files = ['c', ('dir', 'a'), ('dir', 'b')]
        filenames = [path.join(self.temp, *p) for p in files]
        for filename in filenames:
            with open(filename, 'w'):
                pass

        entries = walk([self.temp])
        self.assertListEqual(list(entries), filenames)
