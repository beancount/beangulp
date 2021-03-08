"""Test loader to make unittest test discovery pick up the doctests."""

import doctest
import unittest

def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTest(
        doctest.DocFileSuite(
            'testing.rst',
            optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE))
    return suite

