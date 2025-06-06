__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import unittest
import warnings

from beangulp import importer
from beangulp import cache


class TestImporterProtocol(unittest.TestCase):
    def test_importer_methods(self):
        # Kind of a dumb test, but for consistency we just test everything.
        memo = cache._FileMemo("/tmp/test")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            imp = importer.ImporterProtocol()
        self.assertIsInstance(imp.FLAG, str)
        self.assertFalse(imp.identify(memo))
        self.assertFalse(imp.extract(memo))
        self.assertFalse(imp.file_account(memo))
        self.assertFalse(imp.file_date(memo))
        self.assertFalse(imp.file_name(memo))
