import datetime
import unittest

from beangulp import date_utils


class TestDateUtils(unittest.TestCase):

    def test_parse_date(self):
        self.assertEqual(datetime.date(2021, 7, 4), date_utils.parse_date('2021-07-04'))
