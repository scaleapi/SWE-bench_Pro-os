import json
from pathlib import Path

from swe_bench_pro_eval import prepare_run, write_files_local


def test_attempt_workspaces_are_independent(tmp_path):
    _, output_a, workspace_a = prepare_run("instance", tmp_path, "attempt-a", False)
    _, output_b, workspace_b = prepare_run("instance", tmp_path, "attempt-b", False)

    assert output_a != output_b
    assert workspace_a != workspace_b
    write_files_local(workspace_a, {"patch.diff": "first"})
    write_files_local(workspace_b, {"patch.diff": "second"})
    assert Path(workspace_a, "patch.diff").read_text() == "first"
    assert Path(workspace_b, "patch.diff").read_text() == "second"

    Path(output_a).write_text(json.dumps({"resolved": True}))
    existing, existing_output, existing_workspace = prepare_run("instance", tmp_path, "attempt-a", False)
    assert existing == {"resolved": True}
    assert existing_output == output_a
    assert existing_workspace == workspace_a


def test_prepare_run_preserves_default_workspace_name(tmp_path):
    _, _, workspace = prepare_run("instance", tmp_path, "", False)

    assert workspace == str(tmp_path / "instance" / "workspace")
