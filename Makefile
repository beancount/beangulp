#!/usr/bin/env make

# Test in an isolated Python environment.
# uv python pin <version> to set the version.
test:
	(env -u PYTHONPATH  uv run --isolated --python 3.13  python -m pytest)

test-all:
	for V in 3.7 3.8 3.9 3.10 3.11 3.12 3.13 ; do \
		(env -u PYTHONPATH  uv run --isolated --python $$V  python -m pytest) ; \
	done
