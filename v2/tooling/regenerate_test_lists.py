#!/usr/bin/env python3
"""Regenerate grading lists from N reference and N empty-submission output.json files.

Only pytest node IDs containing :: are supported. Any shipped or measured name
without :: is an error, even if it would otherwise be filtered out.
Only tests whose file exactly matches selected_test_files_to_run are considered
(after normalizing relative POSIX paths). A test must pass in every reference run.
fail_to_pass contains those that never pass in an empty run; pass_to_pass contains
those that pass in every empty run. Changes between passed and not passed within
either group are unstable: exclude and report them. FAILED, ERROR and absence
all count as not passed, so changes among them do not make a test unstable.
Parametrized IDs containing the run's calendar year or next year in their
parameters are date-dependent: exclude and report them unless the exact ID is
already in either shipped grading list. --run-year defaults to the current year.
Repeat --exclude NODE_ID to omit exact IDs with other known instability, such as
test_published_in_future_year[1-True], whose now + 365 days stays in the same
year on January 1 of leap years. Explicit exclusions are reported in
excluded_tests. Shipped names absent from the regenerated lists are reported in
dropped_shipped_tests. Excludes matching no measured or shipped name are reported
in unmatched_excludes. Either report being nonempty, or an empty regenerated
fail_to_pass, exits 1 without writing stdout; pass_to_pass may be empty.
Use the original shipped config as --config when regenerating additions.

--rename-truncated instead preserves shipped order and list membership. Names
observed verbatim stay in place. Each other name expands in place to sorted full
measured IDs whose prefix before the first space equals it, whose file is selected,
and which pass every reference and either never pass an empty run (fail_to_pass)
or pass every empty run (pass_to_pass). Consistently opposite-role IDs are ignored.
One-to-many expansion is allowed; inconsistent run evidence or overlapping ownership
is ambiguous. Missing mappings and ambiguities exit 1 with a JSON report and no
stdout. No other IDs are added, removed, moved or date-filtered. --exclude is
incompatible with this mode. Selections containing node IDs use their file parts
in this mode only; the source selection field is never changed. Stderr reports
renamed_tests, unmapped_shipped_tests and ambiguous_shipped_tests.

Usage:
    python3 v2/tooling/regenerate_test_lists.py --config tests/config.json \
        --reference ref-1/output.json ref-2/output.json \
        --empty empty-1/output.json empty-2/output.json --run-year 2026 \
        > test-lists.json 2> excluded-tests.json
    python3 v2/tooling/regenerate_test_lists.py --rename-truncated \
        --config shipped-config.json --reference ref-1/output.json ref-2/output.json \
        --empty empty-1/output.json empty-2/output.json > renamed-lists.json
    python3 v2/tooling/regenerate_test_lists.py --self-test

The source config is read only. Stdout contains fail_to_pass/pass_to_pass fields,
sorted in the default mode, preserving each field's list or encoded-string type
and encoding style. In the default mode stderr contains sorted unstable_tests,
date_dependent_tests, excluded_tests,
dropped_shipped_tests and unmatched_excludes reports, plus an error message if
fail_to_pass is empty. Unstable statuses follow input-run order; null means
missing. No run execution or config/checksum writes occur.
"""

import argparse
import ast
import json
import posixpath
import subprocess
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory


def load_run(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("tests"), list):
        raise ValueError(f"{path}: expected an object with a tests list")
    results = {}
    for test in data["tests"]:
        if not isinstance(test, dict):
            raise ValueError(f"{path}: expected test objects")
        name, status = test.get("name"), test.get("status")
        if not isinstance(name, str) or not name or not isinstance(status, str) or not status:
            raise ValueError(f"{path}: each test needs a nonempty name and status")
        if name in results and results[name] != status:
            raise ValueError(f"{path}: conflicting statuses for {name}")
        results[name] = status
    return results


def decode_list(value, field):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = ast.literal_eval(value)
    if not isinstance(value, list) or not all(isinstance(p, str) and p for p in value):
        raise ValueError(f"{field} must be a list of nonempty strings")
    return value


def encode_list(tests, template):
    if not isinstance(template, str):
        return tests
    try:
        json.loads(template)
    except ValueError:
        return repr(tests)
    return json.dumps(tests)


def regenerate(reference_runs, empty_runs, selected_files, run_year=None, shipped_names=(),
               excluded_names=()):
    if not reference_runs or len(reference_runs) != len(empty_runs):
        raise ValueError("supply the same nonzero number of reference and empty runs")
    if run_year is None:
        run_year = date.today().year
    years = (str(run_year), str(run_year + 1))
    shipped = set(shipped_names)
    selected = {posixpath.normpath(name) for name in selected_files}
    names = set().union(*reference_runs, *empty_runs)
    unsupported = sorted(name for name in names | shipped if "::" not in name)
    if unsupported:
        raise ValueError("only pytest node IDs containing '::' are supported; "
                         "unsupported test names: " + json.dumps(unsupported))
    excluded = set(excluded_names)
    lists = {"fail_to_pass": [], "pass_to_pass": []}
    unstable = []
    date_dependent = []
    excluded_tests = []
    for name in sorted(names):
        if posixpath.normpath(name.split("::", 1)[0]) not in selected:
            continue
        if name in excluded:
            excluded_tests.append(name)
            continue
        reference = [run.get(name) for run in reference_runs]
        empty = [run.get(name) for run in empty_runs]
        parameters = name.split("::", 1)[-1].partition("[")[2]
        is_date_dependent = (parameters.endswith("]")
                             and any(year in parameters[:-1] for year in years)
                             and name not in shipped)
        if is_date_dependent:
            date_dependent.append(name)
        if (len({status == "PASSED" for status in reference}) > 1
                or len({status == "PASSED" for status in empty}) > 1):
            unstable.append({"name": name, "reference": reference, "empty": empty})
        elif not is_date_dependent and all(status == "PASSED" for status in reference):
            field = "pass_to_pass" if all(status == "PASSED" for status in empty) else "fail_to_pass"
            lists[field].append(name)
    dropped_shipped = sorted(shipped - set().union(*lists.values()))
    return lists, {"unstable_tests": unstable, "date_dependent_tests": date_dependent,
                   "excluded_tests": excluded_tests, "dropped_shipped_tests": dropped_shipped,
                   "unmatched_excludes": sorted(excluded - names - shipped)}


def rename_truncated(reference_runs, empty_runs, selected_files, shipped_lists):
    if not reference_runs or len(reference_runs) != len(empty_runs):
        raise ValueError("supply the same nonzero number of reference and empty runs")
    selected = {posixpath.normpath(name.split("::", 1)[0]) for name in selected_files}
    names = set().union(*reference_runs, *empty_runs)
    shipped = set().union(*shipped_lists.values())
    unsupported = sorted(name for name in names | shipped if "::" not in name)
    if unsupported:
        raise ValueError("only pytest node IDs containing '::' are supported; "
                         "unsupported test names: " + json.dumps(unsupported))
    prefixes = {}
    for name in sorted(names):
        if posixpath.normpath(name.split("::", 1)[0]) in selected:
            prefixes.setdefault(name.split(" ", 1)[0], []).append(name)
    lists = {"fail_to_pass": [], "pass_to_pass": []}
    report = {"renamed_tests": [], "unmapped_shipped_tests": [],
              "ambiguous_shipped_tests": []}
    owners = {}
    for field in lists:
        for name in shipped_lists[field]:
            entry = {"field": field, "name": name}
            replacements = []
            if name in names:
                replacements = [name]
            else:
                for full in prefixes.get(name, []):
                    reference = [run.get(full) for run in reference_runs]
                    empty = [run.get(full) for run in empty_runs]
                    if (len({status == "PASSED" for status in reference}) > 1
                            or len({status == "PASSED" for status in empty}) > 1):
                        report["ambiguous_shipped_tests"].append(
                            {**entry, "candidate": full, "reference": reference,
                             "empty": empty})
                    elif (all(status == "PASSED" for status in reference)
                          and all((status == "PASSED") == (field == "pass_to_pass")
                                  for status in empty)):
                        replacements.append(full)
                if not replacements:
                    report["unmapped_shipped_tests"].append(entry)
                else:
                    report["renamed_tests"].append({**entry, "replacements": replacements})
            for full in replacements:
                if full in owners:
                    report["ambiguous_shipped_tests"].append(
                        {**entry, "candidate": full, "previous_owner": owners[full]})
                owners[full] = entry
            lists[field].extend(replacements)
    return lists, report


def self_test():
    checks = 0

    def check_equal(actual, expected):
        nonlocal checks
        checks += 1
        if actual != expected:
            raise RuntimeError(f"self-test check {checks}: {actual!r} != {expected!r}")

    prefix = "openlibrary/catalog/add_book/tests/test_add_book.py::TestNormalizeImportRecord::"
    test = prefix + "test_future_publication_dates_are_deleted"
    current = test + "[2026-True]"
    following = test + "[2027-False]"
    fixed = [test + "[2000-11-11-True]", test + "[9999-01-01-False]"]
    shipped = test + "[2026-01-01-True]"
    other = prefix + "test_2026_is_not_a_parameter"
    unstable = test + "[unstable]"
    absent = test + "[absent]"
    unselected = "other.py::test_date[2026]"
    reference = dict.fromkeys([current, following, *fixed, shipped, other,
                               unstable, absent, unselected], "PASSED")
    empty = {name: status for name, status in reference.items() if name != absent}
    lists, report = regenerate([reference, reference],
                               [empty, {**empty, unstable: "FAILED"}],
                               ["./openlibrary/catalog/add_book/tests/test_add_book.py"],
                               run_year=2026, shipped_names=[shipped])
    check_equal(lists, {"fail_to_pass": [absent],
                        "pass_to_pass": sorted([*fixed, shipped, other])})
    check_equal(report, {"unstable_tests": [{"name": unstable,
                                             "reference": ["PASSED", "PASSED"],
                                             "empty": ["PASSED", "FAILED"]}],
                         "date_dependent_tests": [current, following],
                         "excluded_tests": [], "dropped_shipped_tests": [],
                         "unmatched_excludes": []})
    lists, report = regenerate([reference], [empty],
                               ["openlibrary/catalog/add_book/tests/test_add_book.py"],
                               run_year=2025)
    check_equal(current in lists["pass_to_pass"], False)
    check_equal(following in lists["pass_to_pass"], True)
    check_equal(report["date_dependent_tests"], sorted([current, shipped]))
    check_equal(decode_list("['test.py::test']", "fail_to_pass"), ["test.py::test"])
    check_equal(decode_list('["test.py::test"]', "pass_to_pass"), ["test.py::test"])
    for template, expected in [([], ["test.py::test"]),
                               ("['old.py::test']", "['test.py::test']"),
                               ('["old.py::test"]', '["test.py::test"]')]:
        check_equal(encode_list(["test.py::test"], template), expected)
        quoted = ["test.py::test[quote's]", 'test.py::test["quoted"]']
        check_equal(decode_list(encode_list(quoted, template), "tests"), quoted)

    # Different non-pass statuses and missing entries are equally stable.
    reference = {test: "PASSED", other: "FAILED"}
    lists, report = regenerate([reference, {**reference, other: "ERROR"}, {test: "PASSED"}],
                               [{test: "FAILED"}, {test: "ERROR"}, {}],
                               ["openlibrary/catalog/add_book/tests/test_add_book.py"],
                               shipped_names=[test])
    check_equal(lists, {"fail_to_pass": [test], "pass_to_pass": []})
    check_equal(report, {"unstable_tests": [], "date_dependent_tests": [],
                         "excluded_tests": [], "dropped_shipped_tests": [],
                         "unmatched_excludes": []})
    lists, report = regenerate([{test: "PASSED"}], [{test: "FAILED"}],
                               ["openlibrary/catalog/add_book/tests/test_add_book.py"],
                               shipped_names=[test, absent, unselected],
                               excluded_names=[test, absent, unselected, "test.py::typo"])
    check_equal(lists, {"fail_to_pass": [], "pass_to_pass": []})
    check_equal(report, {"unstable_tests": [], "date_dependent_tests": [],
                         "excluded_tests": [test],
                         "dropped_shipped_tests": sorted([test, absent, unselected]),
                         "unmatched_excludes": ["test.py::typo"]})
    for unsupported in ["suite should work", "test.js test name", "TestGo/subtest"]:
        for references, empties, shipped_names in [([{unsupported: "PASSED"}], [{}], []),
                                                   ([{}], [{unsupported: "FAILED"}], []),
                                                   ([{}], [{}], [unsupported])]:
            try:
                regenerate(references, empties, ["test.py"], shipped_names=shipped_names)
            except ValueError as exc:
                check_equal("only pytest node IDs" in str(exc) and unsupported in str(exc), True)
            else:
                raise RuntimeError("self-test accepted a non-pytest test name")

    # Exercise CLI exit codes, reports and stdout suppression, also under -O.
    with TemporaryDirectory() as directory:
        directory = Path(directory)
        config_path, reference_path, empty_path = [directory / name for name in
                                                  ("config.json", "reference.json", "empty.json")]
        keep, unselected = "test.py::keep", "other.py::unselected"
        reference_path.write_text(json.dumps({"tests": [
            {"name": name, "status": "PASSED"} for name in (keep, unselected)]}))
        for template in ([], "[]"):
            config_path.write_text(json.dumps({"selected_test_files_to_run": ["test.py"],
                                               "fail_to_pass": template,
                                               "pass_to_pass": template}))
            for status, excludes, expected_code in [
                    ("FAILED", [unselected], 0),
                    ("FAILED", ["test.py::typo-z", "test.py::typo-a"], 1),
                    ("PASSED", [], 1),
                    ("FAILED", [keep], 1)]:
                empty_path.write_text(json.dumps({"tests": [{"name": keep, "status": status}]}))
                command = [sys.executable, "-O", str(Path(__file__).resolve()),
                           "--config", str(config_path), "--reference", str(reference_path),
                           "--empty", str(empty_path), "--run-year", "2026"]
                for name in excludes:
                    command.extend(["--exclude", name])
                result = subprocess.run(command, capture_output=True, text=True)
                check_equal(result.returncode, expected_code)
                report = json.loads(result.stderr)
                if expected_code == 0:
                    check_equal(json.loads(result.stdout),
                                {"fail_to_pass": encode_list([keep], template),
                                 "pass_to_pass": encode_list([], template)})
                    check_equal(report["unmatched_excludes"], [])
                else:
                    check_equal(result.stdout, "")
                    if status == "FAILED" and keep not in excludes:
                        check_equal(report["unmatched_excludes"], sorted(excludes))
                    else:
                        check_equal("regenerated fail_to_pass is empty" in report["error"], True)
    # Rename only: preserve shipped positions, roles and verbatim names, even
    # when a prefix also matches other IDs. Select files from node-ID selections.
    a, b, exact = "test.py::case[a", "test.py::case[b", "test.py::exact"
    full = [a + " one]", a + " two]", b + " 2026]", exact + " extra"]
    reference = dict.fromkeys([exact, *full, "test.py::unshipped"], "PASSED")
    empty = {full[1]: "ERROR", full[2]: "PASSED", full[3]: "PASSED"}
    shipped = {"fail_to_pass": [exact, a], "pass_to_pass": [b]}
    lists, report = rename_truncated([reference, reference], [empty, empty],
                                     ["./test.py::selected"], shipped)
    check_equal(lists, {"fail_to_pass": [exact, *full[:2]], "pass_to_pass": [full[2]]})
    check_equal(report, {"renamed_tests": [
        {"field": "fail_to_pass", "name": a, "replacements": full[:2]},
        {"field": "pass_to_pass", "name": b, "replacements": [full[2]]}],
        "unmapped_shipped_tests": [], "ambiguous_shipped_tests": []})
    # Opposite-role collisions do not move between lists.
    lists, report = rename_truncated([reference], [{**empty, full[1]: "PASSED"}],
                                     ["test.py"], shipped)
    check_equal(lists["fail_to_pass"], [exact, full[0]])
    check_equal(report["ambiguous_shipped_tests"], [])
    for selection, references, empties, source, error in [
            (["other.py"], [reference], [empty], shipped, "unmapped_shipped_tests"),
            (["test.py"], [reference], [empty],
             {"fail_to_pass": ["test.py::missing"], "pass_to_pass": []},
             "unmapped_shipped_tests"),
            (["test.py"], [reference], [empty],
             {"fail_to_pass": [b], "pass_to_pass": []}, "unmapped_shipped_tests"),
            (["test.py"], [reference, reference], [empty, {**empty, full[0]: "PASSED"}],
             shipped, "ambiguous_shipped_tests"),
            (["test.py"], [reference, {**reference, full[0]: "FAILED"}], [empty, empty],
             shipped, "ambiguous_shipped_tests"),
            (["test.py"], [reference], [empty],
             {"fail_to_pass": [a, full[0]], "pass_to_pass": []},
             "ambiguous_shipped_tests")]:
        _, report = rename_truncated(references, empties, selection, source)
        check_equal(bool(report[error]), True)
    # CLI failures must suppress stdout under -O, and preserve encoded types.
    with TemporaryDirectory() as directory:
        directory = Path(directory)
        config_path, reference_path, empty_path = [directory / name for name in
                                                  ("config.json", "reference.json", "empty.json")]
        reference_path.write_text(json.dumps({"tests": [
            {"name": name, "status": status} for name, status in reference.items()]}))
        empty_path.write_text(json.dumps({"tests": [
            {"name": name, "status": status} for name, status in empty.items()]}))
        for template in ([], "[]", "['old.py::test']"):
            for case in ("success", "missing", "ambiguous", "exclude"):
                source = {field: encode_list(tests, template) for field, tests in shipped.items()}
                if case == "missing":
                    source["pass_to_pass"] = encode_list(["test.py::missing"], template)
                elif case == "ambiguous":
                    source["fail_to_pass"] = encode_list([a, full[0]], template)
                config_path.write_text(json.dumps({**source,
                                                   "selected_test_files_to_run": ["test.py::selected"]}))
                command = [sys.executable, "-O", str(Path(__file__).resolve()),
                           "--rename-truncated", "--config", str(config_path),
                           "--reference", str(reference_path), "--empty", str(empty_path)]
                if case == "exclude":
                    command.extend(["--exclude", full[0]])
                result = subprocess.run(command, capture_output=True, text=True)
                check_equal(result.returncode, 0 if case == "success" else 1)
                if case == "success":
                    check_equal(json.loads(result.stdout), {
                        "fail_to_pass": encode_list([exact, *full[:2]], template),
                        "pass_to_pass": encode_list([full[2]], template)})
                else:
                    check_equal(result.stdout, "")
                    report = json.loads(result.stderr)
                    check_equal(bool(report.get({"missing": "unmapped_shipped_tests",
                                                 "ambiguous": "ambiguous_shipped_tests",
                                                 "exclude": "error"}[case])), True)
    print(f"self-test: passed ({checks} checks)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        help="source task config with selected_test_files_to_run")
    parser.add_argument("--reference", nargs="+", type=Path,
                        help="reference output.json files, in run order")
    parser.add_argument("--empty", nargs="+", type=Path,
                        help="empty-submission output.json files, in run order")
    parser.add_argument("--run-year", type=int, default=date.today().year,
                        help="calendar year of the measured runs (default: current year)")
    parser.add_argument("--exclude", action="append", default=[], metavar="NODE_ID",
                        help="exclude an exact pytest node ID and report it (repeatable; "
                             "unmatched IDs and dropping shipped IDs are errors)")
    parser.add_argument("--self-test", action="store_true", help="run built-in checks and exit")
    parser.add_argument("--rename-truncated", action="store_true",
                        help="replace only truncated shipped IDs in place; preserve order and roles")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.config or not args.reference or not args.empty:
        parser.error("--config, --reference and --empty are required")
    try:
        config = json.loads(args.config.read_text())
        if not isinstance(config, dict):
            raise ValueError("config must be a JSON object")
        selected = decode_list(config["selected_test_files_to_run"], "selected_test_files_to_run")
        shipped = set().union(*(decode_list(config[field], field)
                                for field in ("fail_to_pass", "pass_to_pass")))
        if args.rename_truncated:
            lists, report = rename_truncated(
                [load_run(p) for p in args.reference], [load_run(p) for p in args.empty],
                selected, {field: decode_list(config[field], field)
                           for field in ("fail_to_pass", "pass_to_pass")})
            if args.exclude:
                report["error"] = "--exclude cannot be combined with --rename-truncated"
        else:
            lists, report = regenerate([load_run(p) for p in args.reference],
                                       [load_run(p) for p in args.empty], selected,
                                       args.run_year, shipped, args.exclude)
        if not lists["fail_to_pass"]:
            report["error"] = ("regenerated fail_to_pass is empty; at least one test must fail "
                               "on empty submissions")
        for field, tests in lists.items():
            lists[field] = encode_list(tests, config[field])
        output = json.dumps(lists, indent=2) + "\n"
        report_output = json.dumps(report, indent=2) + "\n"
    except (OSError, ValueError, SyntaxError, KeyError) as exc:
        parser.error(str(exc))
    sys.stderr.write(report_output)
    if (any(report.get(field) for field in ("dropped_shipped_tests", "unmatched_excludes",
                                          "unmapped_shipped_tests", "ambiguous_shipped_tests"))
            or "error" in report):
        sys.exit(1)
    sys.stdout.write(output)


if __name__ == "__main__":
    main()
