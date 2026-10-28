#!/usr/bin/env python3
"""Check the 22 pytest parsers changed for full parametrized IDs (Python 3.9+).

Run: python3 v2/tooling/check_parser_regressions.py
Each byte-distinct parser runs twice via the same CLI as its task's test.sh,
on stored stdout and on a temporary copy with a trailing space on every line.
Compare the entire exported output.json, including names, statuses and duplicates.
The explicit task list keeps coverage when just one parser is reverted.

Each stdout fixture starts with lines copied from the verifier's
run-script-stdout.txt in reference-patch and empty-patch runs on the published
task images: ansible 1ee70fc2, 40ade1f8, bec27fb4; openlibrary 9bdfd29f,
f0341c0b; qutebrowser a25e8a09. The 1ee70fc2 excerpts retain trailing spaces;
ANSI bytes are preserved. Remaining lines are fixed synthetic cases for spaces,
nested brackets, shared prefixes, verbose/xdist lines, summary reasons and every
pair of duplicate statuses in both orders, spanning stdout and stderr, plus
rerun-then-pass cases. XFAIL/XPASS handling in every variant, and ANSI
stripping in the openlibrary and qutebrowser parsers, are not exercised because
no saved run of these tasks prints them.
No containers or task test suites are run.
"""

import difflib
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


TASKS = {
    "ansible": """
instance_ansible__ansible-1ee70fc272aff6bf3415357c6e13c5de5b928d9b-v1055803c3a812189a1133297f7f5468579283f86
instance_ansible__ansible-379058e10f3dbc0fdcaf80394bd09b18927e7d33-v1055803c3a812189a1133297f7f5468579283f86
instance_ansible__ansible-3db08adbb1cc6aa9941be5e0fc810132c6e1fa4b-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5
instance_ansible__ansible-40ade1f84b8bb10a63576b0ac320c13f57c87d34-v6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf
instance_ansible__ansible-a20a52701402a12f91396549df04ac55809f68e9-v1055803c3a812189a1133297f7f5468579283f86
instance_ansible__ansible-b748edea457a4576847a10275678127895d2f02f-v1055803c3a812189a1133297f7f5468579283f86
instance_ansible__ansible-be2c376ab87e3e872ca21697508f12c6909cf85a-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5
instance_ansible__ansible-bec27fb4c0a40c5f8bbcf26a475704227d65ee73-v30a923fb5c164d6cd18280c02422f75e611e8fb2
instance_ansible__ansible-d2f80991180337e2be23d6883064a67dcbaeb662-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5
instance_ansible__ansible-d30fc6c0b359f631130b0e979d9a78a7b3747d48-v1055803c3a812189a1133297f7f5468579283f86
instance_ansible__ansible-de5858f48dc9e1ce9117034e0d7e76806f420ca8-v1055803c3a812189a1133297f7f5468579283f86
instance_ansible__ansible-ecea15c508f0e081525be036cf76bbb56dbcdd9d-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5
instance_ansible__ansible-f327e65d11bb905ed9f15996024f857a95592629-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5
instance_ansible__ansible-fb144c44144f8bd3542e71f5db62b6d322c7bd85-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5
""".split(),
    "openlibrary": """
instance_internetarchive__openlibrary-0a90f9f0256e4f933523e9842799e39f95ae29ce-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c
instance_internetarchive__openlibrary-0d13e6b4bf80bced6c0946b969b9a1b6963f6bce-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c
instance_internetarchive__openlibrary-431442c92887a3aece3f8aa771dd029738a80eb1-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c
instance_internetarchive__openlibrary-5c6c22f3d2edf2f1b10f5dc335e32cb6a5f40341-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c
instance_internetarchive__openlibrary-9bdfd29fac883e77dcbc4208cab28c06fd963ab2-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c
instance_internetarchive__openlibrary-ba3abfb6af6e722185d3715929ab0f3e5a134eed-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c
instance_internetarchive__openlibrary-f0341c0ba81c790241b782f5103ce5c9a6edf8e3-ve8fc82d8aae8463b752a211156c5b7b59f349237
""".split(),
    "qutebrowser": """
instance_qutebrowser__qutebrowser-a25e8a09873838ca9efefd36ea8a45170bbeb95c-vc2f56a753b62a190ddb23cd330c257b9cf560d12
""".split(),
}


def main():
    v2 = Path(__file__).resolve().parents[1]
    fixtures = Path(__file__).with_name("parser_fixtures")
    groups = {}
    for fixture, tasks in TASKS.items():
        for task in tasks:
            parser = v2 / "tasks" / task / "tests" / "parser.py"
            digest = hashlib.sha256(parser.read_bytes()).hexdigest()
            groups.setdefault((digest, fixture), []).append(parser)

    failures = 0
    with TemporaryDirectory(prefix="parser-check-") as directory:
        output = Path(directory) / "output.json"
        padded = Path(directory) / "padded.stdout"
        for (digest, fixture), parsers in groups.items():
            print(f"sha256={digest} fixture={fixture}", flush=True)
            for parser in parsers:
                print(f"  {parser.parent.parent.name}", flush=True)
            stdout = fixtures / (fixture + ".stdout")
            padded.write_text(stdout.read_text().replace("\n", " \n"))
            expected = json.loads((fixtures / (fixture + ".json")).read_text())
            failed = False
            for mode, source in [("stored", stdout), ("padded", padded)]:
                output.unlink(missing_ok=True)
                result = subprocess.run(
                    [sys.executable, str(parsers[0]), str(source),
                     str(fixtures / (fixture + ".stderr")), str(output)],
                    capture_output=True, text=True, timeout=30)
                try:
                    if result.returncode:
                        raise ValueError(f"parser exited {result.returncode}: {result.stderr}")
                    actual = json.loads(output.read_text())
                    if actual != expected:
                        diff = "".join(difflib.unified_diff(
                            json.dumps(expected, indent=2).splitlines(keepends=True),
                            json.dumps(actual, indent=2).splitlines(keepends=True),
                            fromfile="expected output.json", tofile="actual output.json"))
                        raise ValueError("exported JSON mismatch\n" + diff)
                except (OSError, ValueError) as exc:
                    failed = True
                    print(f"FAIL {digest} ({mode}): {exc}", file=sys.stderr)
                else:
                    print(f"PASS {mode} ({len(expected['tests'])} exact names/statuses)", flush=True)
            failures += failed
    print(f"parser checks: {len(groups) - failures}/{len(groups)} variants passed "
          f"(stored and padded stdout); "
          f"{sum(map(len, TASKS.values()))} tasks covered")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
