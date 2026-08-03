"""Command-line interface entrypoint and diagnostic commands for Bitheim."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from bitheim import __version__
from bitheim.bootstrap.configuration import ConfigurationError, load_configuration


def _find_nearest_existing_ancestor(path: Path) -> Path | None:
    """Locate the closest existing ancestor directory for a non-existent path."""
    current = path if path.is_absolute() else Path.cwd() / path
    candidate = current.parent
    while not candidate.exists():
        if candidate == candidate.parent:
            return None
        candidate = candidate.parent
    return candidate


def handle_doctor(args: argparse.Namespace) -> int:
    """Execute diagnostic checks for system runtime, configuration, and storage.

    Args:
        args: Parsed command-line arguments for the doctor subcommand.

    Returns:
        0 if all diagnostics pass, 1 if any check or configuration load fails.
    """
    all_passed = True

    # Check 1: Python runtime compatibility (>=3.13)
    if sys.version_info >= (3, 13):  # noqa: UP036
        py_version_str = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        sys.stdout.write(f"[✓] Python runtime: {py_version_str} (compatible with >=3.13)\n")
    else:
        sys.stderr.write(
            f"[✗] Python runtime: {sys.version.split()[0]} is incompatible (requires >=3.13)\n"
        )
        all_passed = False

    # Check 2: Configuration loading and schema validation
    try:
        config = load_configuration(config_path=args.config, data_dir=args.data_dir)
        source = f"file '{config.config_file}'" if config.config_file else "defaults / environment"
        sys.stdout.write(f"[✓] Configuration: loaded successfully ({source})\n")
    except ConfigurationError as err:
        sys.stderr.write(f"[✗] Configuration: {err}\n")
        return 1

    # Check 3 & 4: Effective data directory and filesystem accessibility
    data_dir: Path = config.runtime.data_dir
    sys.stdout.write(f"[✓] Effective data directory: {data_dir}\n")

    if data_dir.exists():
        if not data_dir.is_dir():
            sys.stderr.write(
                f"[✗] Data directory access: '{data_dir}' exists but is not a directory\n"
            )
            all_passed = False
        elif not os.access(data_dir, os.W_OK):
            sys.stderr.write(f"[✗] Data directory access: '{data_dir}' is not writable\n")
            all_passed = False
        else:
            sys.stdout.write("[✓] Data directory access: directory exists and is writable\n")
    else:
        ancestor = _find_nearest_existing_ancestor(data_dir)
        if ancestor is None or not ancestor.exists():
            sys.stderr.write(
                f"[✗] Data directory access: no existing ancestor found for '{data_dir}'\n"
            )
            all_passed = False
        elif not ancestor.is_dir():
            sys.stderr.write(
                f"[✗] Data directory access: nearest ancestor '{ancestor}' is not a directory\n"
            )
            all_passed = False
        elif not os.access(ancestor, os.W_OK):
            sys.stderr.write(
                f"[✗] Data directory access: nearest ancestor '{ancestor}' is not writable\n"
            )
            all_passed = False
        else:
            sys.stdout.write(
                f"[✓] Data directory access: nearest ancestor '{ancestor}' exists and is writable\n"
            )

    return 0 if all_passed else 1


def build_parser() -> argparse.ArgumentParser:
    """Construct and configure the root command-line argument parser.

    Returns:
        Configured ArgumentParser with canonical metadata, standard help,
        version flags, and registered subcommands.
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

    subparsers = parser.add_subparsers(dest="subcommand", required=False)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run system and environment diagnostic checks.",
        description="Run system and environment diagnostic checks.",
    )
    doctor_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to custom configuration file.",
    )
    doctor_parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Override runtime data directory path.",
    )
    doctor_parser.set_defaults(handler=handle_doctor)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the command-line interface with specified argument vector.

    Args:
        argv: Optional sequence of command-line arguments. When None,
            sys.argv[1:] is processed by the underlying parser.

    Returns:
        Integer exit code (0 for success, non-zero on diagnostic or configuration failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "handler") and args.handler is not None:
        try:
            return int(args.handler(args))
        except ConfigurationError as err:
            sys.stderr.write(f"bitheim: error: {err}\n")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
