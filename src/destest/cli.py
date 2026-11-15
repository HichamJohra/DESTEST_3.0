"""Command-line interface: `destest <command> ...`.

    destest check-names "Result data" --recursive       check every file in a folder tree
    destest check-names file1.csv file2.csv             check given files (or bare names)
    destest check-names "Result data" -r --csv report.csv
    destest make-name --data-type ResultData --series DHN --exercise-number 1 \
        --tool TRNSYS --tool-version 2022 --institution TUD \
        --first-name Clemens --last-name Felsmann
    destest specs                                       check the spec files, list the CMEs
    destest convention                                  print the naming rules

Exit codes: 0 = all names valid, 1 = at least one invalid name, 2 = usage problem.
New commands are added as another sub-parser in `build_parser()`. The options of
`make-name` are generated from the fields of `specs/naming_convention.yaml`.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from . import __version__
from .filename_check import (
    NameCheck,
    check_files,
    check_folder,
    check_name,
    describe,
    make_filename,
    print_report,
    write_csv,
)
from .filename_check import convention as conv
from .specs import (
    SpecError,
    cme_spec_path,
    list_cme_specs,
    load_cme_spec_file,
    naming_convention_path,
)


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
    parts: dict[str, object] = {}
    for f in conv.FIELDS:
        if f.kind == "literal":
            continue
        value = getattr(args, f.key)
        if f.kind == "timestamp" and value is not None:
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                flag = "--" + f.key.replace("_", "-")
                print(f"{flag}: use YYYY-MM-DD HH:MM:SS (got '{value}')", file=sys.stderr)
                return 2
        parts[f.key] = value
    try:
        name = make_filename(extension=args.ext, **parts)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(name)
    return 0


def _cmd_convention(args: argparse.Namespace) -> int:
    print(describe())
    return 0


def _cmd_specs(args: argparse.Namespace) -> int:
    print(f"Naming convention: {naming_convention_path()}  OK")
    ok = True
    for name in list_cme_specs():
        _, series, number = name.split("_")
        path = cme_spec_path(series, int(number))
        try:
            spec = load_cme_spec_file(path)
        except SpecError as exc:
            ok = False
            print(f"{name}: FAILED\n{exc}")
            continue
        n_cols = len(spec.result_data.columns)
        print(f"{name}: OK  ({spec.cme.title}; {n_cols} columns; status {spec.cme.status})")
    return 0 if ok else 1


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
    for f in conv.FIELDS:  # one option per part of the name
        if f.kind == "literal":
            continue
        flag = "--" + f.key.replace("_", "-")
        if f.kind == "timestamp":
            m.add_argument(flag, dest=f.key, help="YYYY-MM-DD HH:MM:SS (default: now)")
        elif f.kind == "choice":
            m.add_argument(flag, dest=f.key, required=True, choices=list(f.allowed), help=f.label)
        elif f.kind == "integer":
            m.add_argument(flag, dest=f.key, required=True, type=int, help=f.label)
        else:
            m.add_argument(flag, dest=f.key, required=True, help=f.label)
    m.add_argument("--ext", help="file extension (default: the one for the data type)")
    m.set_defaults(func=_cmd_make_name)

    v = sub.add_parser("convention", help="print the naming convention")
    v.set_defaults(func=_cmd_convention)

    s = sub.add_parser("specs", help="check the spec files and list the CMEs")
    s.set_defaults(func=_cmd_specs)
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
    except (FileNotFoundError, NotADirectoryError, SpecError) as exc:
        print(exc, file=sys.stderr)
        return 2
    return result


if __name__ == "__main__":
    sys.exit(main())
