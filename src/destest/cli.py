"""Command-line interface: `destest <command> ...`.

    destest check-names "Result data" --recursive       check every file in a folder tree
    destest check-names file1.csv file2.csv             check given files (or bare names)
    destest check-names "Result data" -r --csv report.csv
    destest make-name --data-type ResultData --series DHN --exercise-number 1 \
        --tool TRNSYS --tool-version 2022 --institution TUD \
        --first-name Clemens --last-name Felsmann
    destest specs                                       check the spec files, list the CMEs
    destest check-metadata "Result data"                check every ResultMetadata file
    destest metadata-template ResultData_...csv -o FILE  write a pre-filled metadata template
    destest metadata-template CME_DHN_1                 print a blank template for a CME
    destest data-template CME_DHN_1 -o FILE             write an empty ResultData file (header only)
    destest new-submission --series DHN ... -o FOLDER   correctly named ResultData + ResultMetadata
    destest convention                                  print the naming rules

    destest check "Result data"                         everything: names, pairing, content
    destest check-data "Result data"                    content of every ResultData file

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
from .check import FileReport, check_submission_files, check_submissions, format_reports
from .data_check import DataCheck, check_data, check_data_folder, make_data_template
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
from .metadata_check import (
    MetadataCheck,
    check_metadata,
    check_metadata_folder,
    make_template,
    template_for_data_file,
)
from .specs import (
    SpecError,
    cme_spec_path,
    list_cme_specs,
    load_cme_spec_file,
    load_result_metadata_layout,
    naming_convention_path,
    result_metadata_layout_path,
)
from .submission import create_submission


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


def _add_name_arguments(p: argparse.ArgumentParser, skip: tuple[str, ...] = ()) -> None:
    """One option per part of the file name, generated from naming_convention.yaml."""
    for f in conv.FIELDS:
        if f.kind == "literal" or f.key in skip:
            continue
        flag = "--" + f.key.replace("_", "-")
        if f.kind == "timestamp":
            p.add_argument(flag, dest=f.key, help="YYYY-MM-DD HH:MM:SS (default: now)")
        elif f.kind == "choice":
            p.add_argument(flag, dest=f.key, required=True, choices=list(f.allowed), help=f.label)
        elif f.kind == "integer":
            p.add_argument(flag, dest=f.key, required=True, type=int, help=f.label)
        else:
            p.add_argument(flag, dest=f.key, required=True, help=f.label)


def _name_parts(args: argparse.Namespace) -> dict[str, object] | None:
    """The name parts given on the command line; None (after a message) if a date is wrong."""
    parts: dict[str, object] = {}
    for f in conv.FIELDS:
        if f.kind == "literal" or not hasattr(args, f.key):
            continue
        value = getattr(args, f.key)
        if f.kind == "timestamp" and value is not None:
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                flag = "--" + f.key.replace("_", "-")
                print(f"{flag}: use YYYY-MM-DD HH:MM:SS (got '{value}')", file=sys.stderr)
                return None
        parts[f.key] = value
    return parts


def _write_new(path: Path, text: str, force: bool) -> bool:
    """Write a file unless it exists (and --force is not given); report what happened."""
    if path.exists() and not force:
        print(f"{path} exists already; use --force to overwrite.", file=sys.stderr)
        return False
    path.write_text(text, encoding="utf-8")
    print(f"Written: {path}")
    return True


def _cmd_make_name(args: argparse.Namespace) -> int:
    parts = _name_parts(args)
    if parts is None:
        return 2
    try:
        name = make_filename(extension=args.ext, **parts)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(name)
    return 0


def _cmd_data_template(args: argparse.Namespace) -> int:
    parts = args.cme.split("_")
    if not (len(parts) == 3 and parts[0] == "CME" and parts[2].isdigit()):
        print(f"Give a CME such as CME_DHN_1 (got '{args.cme}').", file=sys.stderr)
        return 2
    text = make_data_template(parts[1], int(parts[2]))
    if args.output is None:
        print(text, end="")
        return 0
    return 0 if _write_new(Path(args.output), text, args.force) else 1


def _cmd_new_submission(args: argparse.Namespace) -> int:
    parts = _name_parts(args)
    if parts is None:
        return 2
    try:
        data_file, meta_file = create_submission(args.output, force=args.force, **parts)
    except (ValueError, FileExistsError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Written: {data_file}\nWritten: {meta_file}")
    print("Next: paste your results under the header, fill in the metadata file, then run")
    print(f'  destest check "{data_file.parent}"')
    return 0


def _cmd_convention(args: argparse.Namespace) -> int:
    print(describe())
    return 0


def _cmd_specs(args: argparse.Namespace) -> int:
    print(f"Naming convention: {naming_convention_path()}  OK")
    load_result_metadata_layout()
    print(f"ResultMetadata layout: {result_metadata_layout_path()}  OK")
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
        print(f"{name}: OK  ({spec.cme.full_title}; {n_cols} columns; status {spec.cme.status})")
    return 0 if ok else 1


def _print_metadata_report(checks: list[MetadataCheck], show_ok: bool) -> None:
    labels = {"ok": "OK  ", "warning": "WARN", "error": "FAIL"}
    print(f"Checking {len(checks)} ResultMetadata file{'s' if len(checks) != 1 else ''}\n")
    for c in checks:
        if c.status == "ok" and not show_ok:
            continue
        print(f"[{labels[c.status]}] {c.path}")
        for i in c.errors + c.warnings:
            print(f"         {i.level:<7} {i.field}: {i.message}")
    n_bad = sum(not c.ok for c in checks)
    print(f"\nSummary: {len(checks) - n_bad} valid, {n_bad} with errors.")


def _cmd_check_metadata(args: argparse.Namespace) -> int:
    checks: list[MetadataCheck] = []
    for target in args.paths:
        p = Path(target)
        if p.is_dir():
            checks += check_metadata_folder(p)
        elif p.is_file():
            checks.append(check_metadata(p))
        else:
            print(f"Not found: {p}", file=sys.stderr)
            return 2
    _print_metadata_report(checks, show_ok=not args.errors_only)
    return 0 if all(c.ok for c in checks) else 1


def _cmd_metadata_template(args: argparse.Namespace) -> int:
    target: str = args.target
    parts = target.split("_")
    if len(parts) == 3 and parts[0] == "CME" and parts[2].isdigit():  # e.g. CME_DHN_1
        text = make_template(parts[1], int(parts[2]))
    else:  # a ResultData file (name or path)
        try:
            _, text = template_for_data_file(target)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
    if args.output is None:
        print(text, end="")
        return 0
    out = Path(args.output)
    if out.is_dir():
        if target.startswith("CME_"):
            print("-o: give a file name when the target is a CME.", file=sys.stderr)
            return 2
        out = out / template_for_data_file(target)[0]
    if out.exists() and not args.force:
        print(f"{out} exists already; use --force to overwrite.", file=sys.stderr)
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"Template written to {out}")
    return 0


def _cmd_check_data(args: argparse.Namespace) -> int:
    checks: list[DataCheck] = []
    for target in args.paths:
        p = Path(target)
        if p.is_dir():
            checks += check_data_folder(p)
        elif p.is_file():
            checks.append(check_data(p))
        else:
            print(f"Not found: {p}", file=sys.stderr)
            return 2
    labels = {"ok": "OK  ", "warning": "WARN", "error": "FAIL"}
    print(f"Checking {len(checks)} ResultData file{'s' if len(checks) != 1 else ''}\n")
    for c in checks:
        if c.status == "ok" and args.errors_only:
            continue
        print(f"[{labels[c.status]}] {c.path}")
        for i in c.errors + c.warnings:
            print(f"         {i.level:<7} {i.field}: {i.message}")
    n_bad = sum(not c.ok for c in checks)
    print(f"\nSummary: {len(checks) - n_bad} valid, {n_bad} with errors.")
    return 0 if n_bad == 0 else 1


def _cmd_check(args: argparse.Namespace) -> int:
    reports: list[FileReport] = []
    base: Path | None = None
    for target in args.paths:
        p = Path(target)
        if p.is_dir():
            reports += check_submissions(p)
            base = p if len(args.paths) == 1 else None
        elif p.is_file():
            reports += check_submission_files([p])
        else:
            print(f"Not found: {p}", file=sys.stderr)
            return 2
    print(format_reports(reports, base=base, show_ok=not args.errors_only))
    return 0 if all(r.ok for r in reports) else 1


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
    _add_name_arguments(m)
    m.add_argument("--ext", help="file extension (default: the one for the data type)")
    m.set_defaults(func=_cmd_make_name)

    v = sub.add_parser("convention", help="print the naming convention")
    v.set_defaults(func=_cmd_convention)

    s = sub.add_parser("specs", help="check the spec files and list the CMEs")
    s.set_defaults(func=_cmd_specs)

    ck = sub.add_parser("check", help="check names, pairing and content of result files")
    ck.add_argument("paths", nargs="+", help="folders (searched with sub-folders) or files")
    ck.add_argument("--errors-only", action="store_true", help="list only files with problems")
    ck.set_defaults(func=_cmd_check)

    cd = sub.add_parser("check-data", help="check the content of ResultData files")
    cd.add_argument("paths", nargs="+", help="folders (searched with sub-folders) or files")
    cd.add_argument("--errors-only", action="store_true", help="list only files with problems")
    cd.set_defaults(func=_cmd_check_data)

    cm = sub.add_parser("check-metadata", help="check the content of ResultMetadata files")
    cm.add_argument("paths", nargs="+", help="folders (searched with sub-folders) or files")
    cm.add_argument("--errors-only", action="store_true", help="list only files with problems")
    cm.set_defaults(func=_cmd_check_metadata)

    dt = sub.add_parser("data-template", help="write an empty ResultData file (header only)")
    dt.add_argument("cme", help="the CME, e.g. CME_DHN_1")
    dt.add_argument("-o", "--output", help="file to write (default: print)")
    dt.add_argument("--force", action="store_true", help="overwrite an existing file")
    dt.set_defaults(func=_cmd_data_template)

    ns = sub.add_parser(
        "new-submission",
        help="create an empty, correctly named ResultData file + its pre-filled ResultMetadata",
    )
    _add_name_arguments(ns, skip=(conv.DATA_TYPE_KEY,))
    ns.add_argument("-o", "--output", required=True, help="folder to write to, e.g. CME_DHN_1")
    ns.add_argument("--force", action="store_true", help="overwrite existing files")
    ns.set_defaults(func=_cmd_new_submission)

    mt = sub.add_parser("metadata-template", help="write a ResultMetadata template")
    mt.add_argument(
        "target", help="a ResultData file (pre-fills the template) or a CME, e.g. CME_DHN_1"
    )
    mt.add_argument("-o", "--output", help="file or folder to write to (default: print)")
    mt.add_argument("--force", action="store_true", help="overwrite an existing file")
    mt.set_defaults(func=_cmd_metadata_template)
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
