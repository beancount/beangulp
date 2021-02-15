#!/usr/bin/env python3
"""Migrate old test files to the new one.

This script can be used to convert old test files for beancount.ingest to the
newer scheme where a single expected file is used. For example, this converts:

    2015-06-13.ofx.qbo
    2015-06-13.ofx.qbo.extract
    2015-06-13.ofx.qbo.file_account
    2015-06-13.ofx.qbo.file_date
    2015-06-13.ofx.qbo.file_name

to:

    2015-06-13.ofx.qbo
    2015-06-13.ofx.qbo.beancount

"""

import functools
import os
import re
from os import path
from typing import List

import click


def read_or_empty(filename: str) -> str:
    if path.exists(filename):
        with open(filename) as infile:
            return infile.read().rstrip()
    else:
        return ''


def process_files(filename: str):
    """Rename files around the given absolute filename."""
    account = read_or_empty(filename + ".file_account")
    date = read_or_empty(filename + ".file_date")
    name = read_or_empty(filename + ".file_name")
    extract = read_or_empty(filename + ".extract")
    with open(filename + ".beancount", "w") as outfile:
        pr = functools.partial(print, file=outfile)
        pr(';; Account: {}'.format(account or''))
        pr(';; Date: {}'.format(date or ''))
        pr(';; Name: {}'.format(name or ''))
        if extract:
            pr(extract)
    for ext in [".file_account", ".file_date", ".file_name", ".extract"]:
        if path.exists(filename + ext):
            os.remove(filename + ext)


@click.command()
@click.argument('directories',type=click.Path(exists=True, resolve_path=True), nargs=-1)
def main(directories: List[str]):
    for directory in directories:
        for root, dirs, files in os.walk(directory):
            for filename in sorted(files):
                afilename = path.join(root, filename)
                if re.search(r"\.(py|beancount)$", afilename):
                    continue
                if re.search(r"\.(extract|file_account|file_name|file_date)", afilename):
                    continue
                if path.exists(afilename + ".beancount"):
                    continue
                process_files(afilename)


if __name__ == '__main__':
    main()
