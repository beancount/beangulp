"""Test loader to make unittest test discovery pick up the doctests."""

import doctest
import unittest


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTest(
        doctest.DocFileSuite(
            'archive.rst',
            'extract.rst',
            'identify.rst',
            'testing.rst',
            optionflags=(
                doctest.ELLIPSIS |
                doctest.NORMALIZE_WHITESPACE |
                doctest.REPORT_NDIFF |
                # Display only the first failed test. Note that all
                # tests are run, thus the cleanup at the end of the
                # doctests file is still executed.
                doctest.REPORT_ONLY_FIRST_FAILURE)))
    return suite
