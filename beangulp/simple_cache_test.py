import os
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta

from beangulp import simple_cache


class SimpleCacheTest(unittest.TestCase):
    """Test the simple_cache module."""

    def setUp(self):
        """Set up a temporary directory for cache files."""
        self.tempdir = tempfile.mkdtemp()
        self.original_cachedir = simple_cache.CACHEDIR
        simple_cache.CACHEDIR = os.path.join(self.tempdir, "cache")

        # Create a test file
        self.test_file = os.path.join(self.tempdir, "test.txt")
        with open(self.test_file, "w") as f:
            f.write("test content")

    def tearDown(self):
        """Clean up the temporary directory."""
        simple_cache.CACHEDIR = self.original_cachedir

    def test_convert_creates_cache_dir(self):
        """Test that the cache directory is created if it doesn't exist."""

        def converter(filename):
            return "converted content"

        simple_cache.convert(self.test_file, converter)
        self.assertTrue(os.path.exists(simple_cache.CACHEDIR))

    def test_convert_caches_result(self):
        """Test that the result is cached."""
        call_count = 0

        def converter(filename):
            nonlocal call_count
            call_count += 1
            return f"converted content {call_count}"

        # First call should execute the converter
        result1 = simple_cache.convert(self.test_file, converter)
        self.assertEqual(result1, "converted content 1")
        self.assertEqual(call_count, 1)

        # Second call should use the cached result
        result2 = simple_cache.convert(self.test_file, converter)
        self.assertEqual(result2, "converted content 1")
        self.assertEqual(call_count, 1)  # Converter not called again

    def test_different_converters_different_cache(self):
        """Test that different converter functions use different cache entries."""

        def converter1(filename):
            return "result from converter1"

        def converter2(filename):
            return "result from converter2"

        result1 = simple_cache.convert(self.test_file, converter1)
        result2 = simple_cache.convert(self.test_file, converter2)

        self.assertEqual(result1, "result from converter1")
        self.assertEqual(result2, "result from converter2")

    def test_different_files_different_cache(self):
        """Test that different files use different cache entries."""
        test_file2 = os.path.join(self.tempdir, "test2.txt")
        with open(test_file2, "w") as f:
            f.write("different content")

        def converter(filename):
            with open(filename, "r") as f:
                return f"converted: {f.read()}"

        result1 = simple_cache.convert(self.test_file, converter)
        result2 = simple_cache.convert(test_file2, converter)

        self.assertEqual(result1, "converted: test content")
        self.assertEqual(result2, "converted: different content")

    def test_cache_filename_generation(self):
        """Test that the cache filename is based on file path and converter."""

        def converter(filename):
            return "result"

        with mock.patch("pickle.dump") as mock_dump:
            simple_cache.convert(self.test_file, converter)

            # Check that pickle.dump was called (cache was written)
            self.assertTrue(mock_dump.called)

            # Get the filename that was used
            cache_file = os.path.dirname(mock_dump.call_args[0][1].name)

            # Verify it's in the cache directory
            self.assertEqual(cache_file, simple_cache.CACHEDIR)

    def test_sentinel_file_creation(self):
        """Test that the sentinel file is created."""

        def converter(filename):
            return "result"

        # Make sure the sentinel file doesn't exist
        sentinel_path = os.path.join(
            simple_cache.CACHEDIR, simple_cache.GC_SENTINEL_FILENAME
        )
        if os.path.exists(sentinel_path):
            os.remove(sentinel_path)

        # Call convert, which should create the sentinel file
        simple_cache.convert(self.test_file, converter)

        # Check that the sentinel file was created
        self.assertTrue(os.path.exists(sentinel_path))

    def test_cleanup_old_files(self):
        """Test that old cache files are cleaned up."""

        # Create some fake old cache files
        os.makedirs(simple_cache.CACHEDIR, exist_ok=True)
        old_file = os.path.join(simple_cache.CACHEDIR, "old_file.pickle")
        with open(old_file, "w") as f:
            f.write("old content")

        # Set the modification time to be older than the threshold
        old_time = datetime.now() - timedelta(days=simple_cache.GC_THRESHOLD_DAYS + 1)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

        # Create a sentinel file with an old timestamp
        sentinel_path = os.path.join(
            simple_cache.CACHEDIR, simple_cache.GC_SENTINEL_FILENAME
        )
        with open(sentinel_path, "w") as f:
            f.write(str(old_time.timestamp()))
        os.utime(sentinel_path, (old_time.timestamp(), old_time.timestamp()))

        # Call convert, which should trigger cleanup
        def converter(filename):
            return "result"

        with mock.patch("os.remove") as mock_remove:
            simple_cache.convert(self.test_file, converter)

            # Check that os.remove was called for the old file
            mock_remove.assert_called()

        # Check that the sentinel file was updated (newer timestamp)
        self.assertGreater(os.path.getmtime(sentinel_path), old_time.timestamp())
