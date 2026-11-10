import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPT = textwrap.dedent("""
    import datetime

    from beancount.core import amount, data
    from beancount.core.number import D

    import beangulp
    from beangulp import importer


    class Importer(importer.Importer):
        name = "test"

        def identify(self, filepath):
            return True

        def account(self, filepath):
            return "Assets:Cash"

        def date(self, filepath):
            return datetime.date(2026, 1, 1)

        def filename(self, filepath):
            return None

        def extract(self, filepath, existing):
            posting = data.Posting(
                "Assets:Cash", amount.Amount(D("1"), "USD"), None, None, None, None
            )
            return [
                data.Transaction(
                    data.new_metadata(filepath, 1),
                    datetime.date(2026, 1, 1),
                    "*",
                    None,
                    "Payment from \\u7ba1\\u8ca1\\u4eba",
                    data.EMPTY_SET,
                    data.EMPTY_SET,
                    [posting],
                )
            ]


    beangulp.Ingest([Importer()])()
""")


class TestExtractOutputFile(unittest.TestCase):
    def test_extract_output_file_is_utf8(self):
        # Run in a subprocess with an ASCII default encoding, as it is the case for the
        # default encoding on Windows or with a C locale.
        env = dict(os.environ, PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", LC_ALL="C")
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source.txt")
            output = os.path.join(tmp, "output.bean")
            script = os.path.join(tmp, "ingest.py")
            with open(source, "w") as fd:
                fd.write("data")
            with open(script, "w") as fd:
                fd.write(SCRIPT)
            result = subprocess.run(
                [sys.executable, script, "extract", "-o", output, source],
                env=env,
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(output, encoding="utf-8") as fd:
                self.assertIn("Payment from 管財人", fd.read())


if __name__ == "__main__":
    unittest.main()
