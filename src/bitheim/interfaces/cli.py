"""Command-line interface entrypoint for Bitheim."""

import argparse
import sys
from collections.abc import Sequence

from bitheim import __version__


def build_parser() -> argparse.ArgumentParser:
    """Construct and configure the root command-line argument parser.

    Returns:
        Configured ArgumentParser with canonical metadata, standard help,
        and version flags.
    """
    parser = argparse.ArgumentParser(
        prog="bitheim",
        description="Distributed platform for experimentation, mining, and analysis on Bitcoin.",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the command-line interface with specified argument vector.

    Args:
        argv: Optional sequence of command-line arguments. When None,
            sys.argv[1:] is processed by the underlying parser.

    Returns:
        Integer exit code (0 for success).
    """
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
