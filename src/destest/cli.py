"""Command-line interface: `destest <command> ...`.

    destest check-names "Result data" --recursive       check every file in a folder tree
    destest check-names file1.csv file2.csv             check given files (or bare names)
    destest check-names "Result data" -r --csv report.csv
    destest make-name --series DHN --number 1 --data-type ResultData --tool TRNSYS \
        --tool-version 2022 --institution TUD --first-name Clemens --last-name Felsmann
    destest convention                                  print the naming rules

Exit codes: 0 = all names valid, 1 = at least one invalid name, 2 = usage problem.
New commands are added as another sub-parser in `build_parser()`.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from . import __version__
from .naming import (
    NameCheck,
    check_files,
    check_folder,
    check_name,
    describe,
    make_filename,
    print_report,
    write_csv,
)
from .naming.convention import DATA_TYPES, SERIES


def _cmd_check_names(args: argparse.Namespace) -> int:
    checks: list[NameCheck] = []
    base: Path | None = None
    for target in args.paths:
        p = Path(target)
        if p.is_dir():
            checks += check_folder(p, recursive=args.recursive)
            base = p if len(args.paths) == 1 else None
        elif p.is_file():
            checks += check_files([p])
        else:  # not on disk: treat the argument as a bare file name to check
            checks.append(check_name(target))
    print_report(checks, base=base, show_ok=not args.errors_only)
    if args.csv:
        out = write_csv(checks, args.csv, base=base)
        print(f"\nReport written to {out}")
    return 0 if all(c.ok for c in checks) else 1


def _cmd_make_name(args: argparse.Namespace) -> int:
    created = None
    if args.created:
        try:
            created = datetime.fromisoformat(args.created)
        except ValueError:
            print(f"--created: use YYYY-MM-DD HH:MM:SS (got '{args.created}')", file=sys.stderr)
            return 2
    try:
        name = make_filename(
            series=args.series,
            number=args.number,
            data_type=args.data_type,
            tool=args.tool,
            tool_version=args.tool_version,
            institution=args.institution,
            first_name=args.first_name,
            last_name=args.last_name,
            created=created,
            extension=args.ext,
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(name)
    return 0


def _cmd_convention(args: argparse.Namespace) -> int:
    print(describe())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The argument parser with all sub-commands."""
    p = argparse.ArgumentParser(
        prog="destest", description="Tools for the DESTEST common modelling exercises."
    )
    p.add_argument("--version", action="version", version=f"destest {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    c = sub.add_parser("check-names", help="check that result files follow the naming convention")
    c.add_argument("paths", nargs="+", help="folders, files or bare file names")
    c.add_argument("-r", "--recursive", action="store_true", help="include sub-folders")
    c.add_argument("--csv", metavar="FILE", help="also write the results to a CSV file")
    c.add_argument("--errors-only", action="store_true", help="list only files with problems")
    c.set_defaults(func=_cmd_check_names)

    m = sub.add_parser("make-name", help="build a correct result-file name")
    m.add_argument("--series", required=True, choices=list(SERIES))
    m.add_argument("--number", required=True, type=int)
    m.add_argument("--data-type", required=True, choices=list(DATA_TYPES))
    m.add_argument("--tool", required=True)
    m.add_argument("--tool-version", required=True)
    m.add_argument("--institution", required=True)
    m.add_argument("--first-name", required=True)
    m.add_argument("--last-name", required=True)
    m.add_argument("--created", help="YYYY-MM-DD HH:MM:SS (default: now)")
    m.add_argument("--ext", default=".csv", help="file extension (default .csv)")
    m.set_defaults(func=_cmd_make_name)

    v = sub.add_parser("convention", help="print the naming convention")
    v.set_defaults(func=_cmd_convention)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the `destest` command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        result: int = args.func(args)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 2
    return result


if __name__ == "__main__":
    sys.exit(main())
