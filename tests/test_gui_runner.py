from datetime import datetime

from tc1d.gui.config import default_config, parse_yaml_text
from tc1d.gui.runner import (
    PACKAGE_SRC,
    build_command,
    build_run_directory,
    build_subprocess_env,
    collect_result_files,
    missing_required_executables,
    prepare_run,
)


def test_build_command_uses_module_cli():
    command = build_command("/tmp/input.yaml", python_executable="python")

    assert command == [
        "python",
        "-m",
        "tc1d.gui.cli_entry",
        "--input-file",
        "/tmp/input.yaml",
    ]


def test_build_run_directory_uses_timestamp_and_clean_label(tmp_path):
    run_dir = build_run_directory(
        tmp_path,
        run_name="Model A!",
        now=datetime(2026, 6, 5, 10, 30, 1),
    )

    assert run_dir == tmp_path / "20260605-103001-Model-A"


def test_prepare_run_writes_generated_yaml(tmp_path):
    config = default_config()
    config["output"]["model_id"] = "smoke"

    prepared = prepare_run(
        config,
        tmp_path,
        run_name="smoke",
        python_executable="python",
    )

    assert prepared.run_dir.exists()
    assert prepared.config_path.exists()
    assert prepared.command[0] == "python"
    reparsed = parse_yaml_text(prepared.config_path.read_text(encoding="utf-8"))
    assert reparsed["output"]["model_id"] == "smoke"


def test_collect_result_files_finds_csv_and_png(tmp_path):
    csv_dir = tmp_path / "csv"
    png_dir = tmp_path / "png"
    csv_dir.mkdir()
    png_dir.mkdir()
    csv_file = csv_dir / "age_summary.csv"
    png_file = png_dir / "thermal_history.png"
    csv_file.write_text("a,b\n", encoding="utf-8")
    png_file.write_bytes(b"not a real png")

    assert collect_result_files(tmp_path) == [png_file, csv_file]


def test_missing_required_executables_uses_path_lookup(monkeypatch):
    monkeypatch.setattr("tc1d.gui.runner.shutil.which", lambda _name, path=None: None)

    assert missing_required_executables(("RDAAM_He",)) == ["RDAAM_He"]


def test_subprocess_env_uses_absolute_source_path(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "src")

    env = build_subprocess_env()

    assert env["PYTHONPATH"].split(":")[0] == str(PACKAGE_SRC)
