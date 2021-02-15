#!/bin/bash
# Run all the regression tests.
DATA=../importers_tests
python3 acme.py   test $DATA/acme
python3 utrade.py test $DATA/utrade
