"""Identify similar entries.

This can be used during import in order to identify and flag duplicate entries.
"""
__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import collections
import datetime

from beancount.core.number import D
from beancount.core.number import ZERO
from beancount.core.number import ONE
from beancount.core import data
from beancount.core import amount
from beancount.core import interpolate


try:
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache(maxsize=None)


def find_similar_entries(entries, existing_entries, cmp=None, window_days=2):
    """Find which entries from a list are potential duplicates of a set.

    The existing_entries array must be sorted by date. If there are
    multiple entries in existing_entries matching an entry in entries,
    only the first match is returned.

    Args:
      entries: The list of entries to classify as duplicate or note.
      existing_entries: The list of entries against which to match.
      comparator: A functor used to establish the similarity of two entries.
      window_days: The number of days (inclusive) before or after to scan the
        entries to classify against.

    Returns:
      A list of (entry, existing_entry) tuples where entry is from
      entries and is deemed to be a duplicate of existing_entry, from
      existing_entries.

    """
    window_head = datetime.timedelta(days=window_days)
    window_tail = datetime.timedelta(days=window_days + 1)

    if cmp is None:
        cmp = comparator()

    # For each of the new entries, look at existing entries at a nearby date.
    duplicates = []
    if existing_entries is not None:
        for entry in data.filter_txns(entries):
            for existing_entry in data.filter_txns(
                    data.iter_entry_dates(existing_entries,
                                          entry.date - window_head,
                                          entry.date + window_tail)):
                if cmp(entry, existing_entry):
                    duplicates.append((entry, existing_entry))
                    break
    return duplicates


class hashable:
    def __init__(self, obj):
        self.obj = obj

    def __hash__(self):
        return id(self.obj)

    def __getattr__(self, name):
        return getattr(self.obj, name)


def comparator(max_date_delta=None, epsilon=None):
    """Comparison function generator."""

    if epsilon is None:
        epsilon = decimal.Decimal('0.05')

    def cmp(entry1, entry2):
        """Compare two entries.

        Determine if two transactions are similar enough to be
        considered duplicates. Other entry types are ignored.

        Args:
          entry1: First entry.
          entry2: Second entry.

        Returns:
          True if they are deemed duplicates, False otherwise.

        """
        # This comparator needs to be able to handle Transaction
        # instances which are incomplete on one side, which have
        # slightly different dates, or potentially postings with
        # slightly different amounts.

        if not isinstance(entry1, data.Transaction) or not isinstance(entry2, data.Transaction):
            return False

        # Check the date difference.
        if max_date_delta is not None:
            delta = ((entry1.date - entry2.date)
                     if entry1.date > entry2.date else
                     (entry2.date - entry1.date))
            if delta > max_date_delta:
                return False

        amounts1 = amounts_map_cached(hashable(entry1))
        amounts2 = amounts_map_cached(hashable(entry2))

        # Look for amounts on common accounts.
        common_keys = set(amounts1) & set(amounts2)
        for key in sorted(common_keys):
            # Compare the amounts.
            number1 = amounts1[key]
            number2 = amounts2[key]
            if number1 == ZERO and number2 == ZERO:
                break
            diff = abs((number1 / number2)
                       if number2 != ZERO
                       else (number2 / number1))
            if diff == ZERO:
                return False
            if diff < ONE:
                diff = ONE/diff
            if (diff - ONE) < epsilon:
                break
        else:
            return False

        # Here, we have found at least one common account with a close
        # amount. Now, we require that the set of accounts are equal or that
        # one be a subset of the other.
        accounts1 = set(posting.account for posting in entry1.postings)
        accounts2 = set(posting.account for posting in entry2.postings)
        return accounts1.issubset(accounts2) or accounts2.issubset(accounts1)

    return cmp


def amounts_map(entry):
    """Compute a mapping of (account, currency) -> Decimal balances.

    Args:
      entry: A Transaction instance.
    Returns:
      A dict of account -> Amount balance.
    """
    amounts = collections.defaultdict(D)
    for posting in entry.postings:
        # Skip interpolated postings.
        if posting.meta and interpolate.AUTOMATIC_META in posting.meta:
            continue
        currency = isinstance(posting.units, amount.Amount) and posting.units.currency
        if isinstance(currency, str):
            key = (posting.account, currency)
            amounts[key] += posting.units.number
    return amounts


amounts_map_cached = cache(amounts_map)
