"""A very simple cache mechanism for expensive file conversions.

Usage:

- You need to explicitly call this from your importers in order to benefit from
  caching. Nothing in beangulp calls this automatically for you.

- You provide a filename and a function to call:

      def extract(file_path):
          ...
          text = simple_cache.convert(file_path, slow_pdf2txt_converter)
          ...

  If the call has been made before and the file hasn't changed nor the function
  definition, you will get the result of the conversion from a file that was
  pickled on the first call.

- The cache will be automatically cleaned up periodically. We leave a sentinel
  file for cleaning and if enough time has gone by we scan the timestamps of the
  cache contents and delete old files.

Note: This supersedes the beangulp.cache module, which should get deleted at
some point.
"""

import os
import pickle
import sys
from os import path
from datetime import datetime, timedelta

from typing import Any, Callable


# Default location of cache directories.
CACHEDIR = (
    path.expandvars("%LOCALAPPDATA%\\Beangulp\\simple_cache")
    if sys.platform == "win32"
    else path.expanduser("~/.cache/beangulp/simple_cache")
)

GC_SENTINEL_FILENAME = "last_cleanup"  # Sentinel file to track last cleanup
GC_SENTINEL_PATH = os.path.join(CACHEDIR, GC_SENTINEL_FILENAME)

# Garbage collection settings
GC_THRESHOLD_DAYS = 7  # Clean files older than 7 days


ConverterFunc = Callable[[str], Any]


def _cleanup_old_cache_files():
    """Clean up cache files older than the threshold.

    This function scans all files in the cache directory and removes
    any that are older than GC_THRESHOLD_DAYS.
    """
    now = datetime.now()
    threshold = now - timedelta(days=GC_THRESHOLD_DAYS)
    threshold_timestamp = threshold.timestamp()

    # Scan all files in the cache directory
    for filename in os.listdir(CACHEDIR):
        if filename == GC_SENTINEL_FILENAME:
            continue

        filepath = os.path.join(CACHEDIR, filename)
        if os.path.isfile(filepath):
            # Check file modification time.
            mtime = os.path.getmtime(filepath)
            if mtime < threshold_timestamp:
                try:
                    os.remove(filepath)
                except OSError:
                    # Ignore errors when removing files.
                    pass

    # Update the sentinel file timestamp.
    gc_sentinel_path = os.path.join(CACHEDIR, GC_SENTINEL_FILENAME)
    with open(gc_sentinel_path, "w") as f:
        f.write(str(now.timestamp()))


def convert(file_path: str, converter: ConverterFunc) -> Any:
    """Convert a file using the provided converter function.

    This will cache the result in a file in the cache directory.
    The cache is cleaned up periodically.
    """
    # Create the cache directory if it doesn't exist.
    os.makedirs(CACHEDIR, exist_ok=True)

    # Check if we need to clean up old cache files.
    gc_sentinel_path = os.path.join(CACHEDIR, GC_SENTINEL_FILENAME)
    if not os.path.exists(gc_sentinel_path):
        # First time, create the sentinel file.
        with open(gc_sentinel_path, "w") as cache_file:
            cache_file.write(str(datetime.now().timestamp()))
    else:
        # Check if it's time to clean up.
        sentinel_mtime = os.path.getmtime(gc_sentinel_path)
        threshold_time = datetime.now() - timedelta(days=GC_THRESHOLD_DAYS)
        if sentinel_mtime < threshold_time.timestamp():
            _cleanup_old_cache_files()

    # Create a unique cache filename based on the file path and converter.
    file_hash = hash(file_path)
    converter_hash = hash(converter.__code__)
    cache_filename = os.path.join(CACHEDIR, f"{file_hash}_{converter_hash}.pickle")

    # Check if the cache file exists and is still valid.
    if os.path.exists(cache_filename):
        with open(cache_filename, "rb") as cache_file:
            return pickle.load(cache_file)

    # Call the converter function and save the result to the cache.
    result = converter(file_path)
    with open(cache_filename, "wb") as cache_file:
        pickle.dump(result, cache_file)

    return result
