"""Executable module entry point for python -m app.lab."""

import sys

from app.lab.cli import main

if __name__ == "__main__":
    sys.exit(main())
