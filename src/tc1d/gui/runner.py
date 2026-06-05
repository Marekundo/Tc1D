"""Subprocess runner for the Tc1D desktop GUI.

The runner is the boundary between the GUI and Tc1D proper. It writes the GUI
config to disk, starts the existing CLI in a subprocess, and keeps runtime
environment tweaks out of the scientific modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from .config import dump_yaml, normalize_config, validate_config


REQUIRED_EXECUTABLES = ("RDAAM_He", "ketch_aft")
REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_EXECUTABLE_DIRS = (
    REPO_ROOT / "src" / "RDAAM_He",
    REPO_ROOT / "src" / "ketch_aft",
    Path.home() / ".local" / "bin",
)
PACKAGE_SRC = REPO_ROOT / "src"
LOCAL_VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
RUNTIME_CACHE_DIR = REPO_ROOT / ".tc1d_gui_cache"
def _default_shim_dir() -> Path:
    """Return a per-user, space-free directory for executable shims.

    Tc1D's scientific code invokes Tc_core executables through shell commands,
    so the shim path must avoid spaces (repository paths often contain them)
    while leaving the underlying scientific code unchanged. The system temp dir
    is space-free, and a uid suffix keeps runs from different users separate on
    a shared ``/tmp``.
    """
    base = Path(tempfile.gettempdir())
    getuid = getattr(os, "getuid", None)
    suffix = f"_{getuid()}" if getuid is not None else ""
    return base / f"tc1d_gui_bin{suffix}"


EXECUTABLE_SHIM_DIR = _default_shim_dir()


@dataclass(frozen=True)
class PreparedRun:
    """Files and command needed to launch a Tc1D run."""

    config: dict[str, Any]
    run_dir: Path
    config_path: Path
    command: list[str]


def missing_required_executables(
    executables: tuple[str, ...] = REQUIRED_EXECUTABLES,
) -> list[str]:
    """Return required thermochronometer executables missing from PATH."""
    path = build_executable_path()
    return [
        executable
        for executable in executables
        if shutil.which(executable, path=path) is None
    ]


def build_executable_path() -> str:
    """Return PATH with bundled/local Tc_core executable directories prepended."""
    existing_path = os.environ.get("PATH", "")
    shim_dir = prepare_executable_shims()
    local_dirs = [str(shim_dir)] if shim_dir is not None else []
    local_dirs.extend(str(path) for path in LOCAL_EXECUTABLE_DIRS if path.exists())
    if not local_dirs:
        return existing_path
    return os.pathsep.join([*local_dirs, existing_path])


def prepare_executable_shims() -> Path | None:
    """Expose local executables through a no-space path for Tc1D shell calls."""
    rdaam_source = REPO_ROOT / "src" / "RDAAM_He" / "RDAAM_He"
    ketch_source = REPO_ROOT / "src" / "ketch_aft" / "ketch_aft"
    if not rdaam_source.exists() and not ketch_source.exists():
        return None

    EXECUTABLE_SHIM_DIR.mkdir(parents=True, exist_ok=True)
    if rdaam_source.exists():
        _copy_executable_shim(rdaam_source, EXECUTABLE_SHIM_DIR / "RDAAM_He")
    if ketch_source.exists():
        _prepare_ketch_shim(EXECUTABLE_SHIM_DIR / "ketch_aft", fallback=ketch_source)
    return EXECUTABLE_SHIM_DIR


def _copy_executable_shim(source: Path, target: Path) -> None:
    """Copy an executable into the shim directory, refreshing stale copies."""
    if _shim_is_current(source, target):
        return
    if target.exists() or target.is_symlink():
        target.unlink()
    shutil.copy2(source, target)


def _shim_is_current(source: Path, target: Path) -> bool:
    """Return True if a copied shim already matches the source executable."""
    if target.is_symlink() or not target.exists():
        return False
    source_stat = source.stat()
    target_stat = target.stat()
    # shutil.copy2 preserves mtime, so a fresh copy has an equal timestamp; a
    # rebuilt (newer) source makes the shim stale and triggers a re-copy.
    return (
        target_stat.st_size == source_stat.st_size
        and target_stat.st_mtime >= source_stat.st_mtime
    )


def _prepare_ketch_shim(target: Path, fallback: Path) -> None:
    """Build or copy a ketch_aft shim, rebuilding when its sources change."""
    source_dir = REPO_ROOT / "src" / "ketch_aft"
    sources = (source_dir / "ketch.c", source_dir / "ketch_aft.c")
    if _ketch_shim_is_current(target, sources):
        return
    if target.exists() or target.is_symlink():
        target.unlink()

    command = [
        "gcc",
        "-O2",
        "-fno-stack-protector",
        "-I",
        str(source_dir),
        "-o",
        str(target),
        str(source_dir / "ketch.c"),
        str(source_dir / "ketch_aft.c"),
        "-lm",
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        shutil.copy2(fallback, target)


def _ketch_shim_is_current(target: Path, sources: tuple[Path, ...]) -> bool:
    """Return True if a built ketch_aft shim is newer than all of its sources."""
    if target.is_symlink() or not target.exists():
        return False
    target_mtime = target.stat().st_mtime
    return all(
        source.exists() and source.stat().st_mtime <= target_mtime
        for source in sources
    )


def build_run_directory(
    output_root: str | Path,
    run_name: str = "",
    now: datetime | None = None,
) -> Path:
    """Create a stable per-run directory name from a timestamp and optional label."""
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    label = _clean_run_label(run_name)
    dirname = f"{timestamp}-{label}" if label else f"{timestamp}-tc1d-run"
    return Path(output_root).expanduser().resolve() / dirname


def build_command(
    config_path: str | Path,
    python_executable: str | None = None,
) -> list[str]:
    """Build the command used by the GUI runner."""
    executable = python_executable or model_python_executable()
    return [
        executable,
        "-m",
        "tc1d.gui.cli_entry",
        "--input-file",
        str(Path(config_path)),
    ]


def prepare_run(
    config: dict[str, Any],
    output_root: str | Path,
    run_name: str = "",
    python_executable: str | None = None,
) -> PreparedRun:
    """Validate config, create the run directory, and write generated YAML."""
    normalized = normalize_config(config)
    errors = validate_config(normalized)
    if errors:
        raise ValueError("\n".join(errors))

    # Tc1D writes its csv/ and png/ outputs relative to cwd. A fresh run folder
    # keeps outputs from different GUI runs separate and easy to inspect.
    run_dir = build_run_directory(output_root, run_name)
    run_dir.mkdir(parents=True, exist_ok=False)
    config_path = run_dir / "tc1d_gui_input.yaml"
    config_path.write_text(dump_yaml(normalized), encoding="utf-8")
    command = build_command(config_path, python_executable=python_executable)
    return PreparedRun(
        config=normalized,
        run_dir=run_dir,
        config_path=config_path,
        command=command,
    )


def model_python_executable() -> str:
    """Return the Python interpreter used for Tc1D model subprocesses."""
    # Prefer a project-local environment when present, because GUI users often
    # launch Tkinter with a system Python that lacks Tc1D's scientific deps.
    if LOCAL_VENV_PYTHON.exists():
        return str(LOCAL_VENV_PYTHON)
    return sys.executable


def start_process(prepared_run: PreparedRun) -> subprocess.Popen[str]:
    """Start a prepared Tc1D run."""
    env = build_subprocess_env()
    return subprocess.Popen(
        prepared_run.command,
        cwd=prepared_run.run_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )


def build_subprocess_env() -> dict[str, str]:
    """Build the environment used for Tc1D subprocesses."""
    env = os.environ.copy()
    env["PATH"] = build_executable_path()
    mpl_cache = RUNTIME_CACHE_DIR / "matplotlib"
    xdg_cache = RUNTIME_CACHE_DIR / "xdg"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    xdg_cache.mkdir(parents=True, exist_ok=True)
    # Headless plotting avoids macOS GUI-backend crashes while still allowing
    # Tc1D to write PNG files for the results tab.
    env["MPLCONFIGDIR"] = str(mpl_cache)
    env["XDG_CACHE_HOME"] = str(xdg_cache)
    env["MPLBACKEND"] = "Agg"
    env.setdefault("OMPI_MCA_btl", "^tcp")

    # The subprocess usually runs from a timestamped output directory, so the
    # source tree must be on PYTHONPATH for editable/source-tree workflows.
    pythonpath_parts = [str(PACKAGE_SRC)]
    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def collect_result_files(run_dir: str | Path) -> list[Path]:
    """Return generated CSV and PNG files for a completed run."""
    root = Path(run_dir)
    files: list[Path] = []
    for subdir, pattern in (("png", "*.png"), ("csv", "*.csv")):
        output_dir = root / subdir
        if output_dir.exists():
            files.extend(sorted(output_dir.glob(pattern)))
    return files


def _clean_run_label(label: str) -> str:
    """Make a filesystem-friendly run label while preserving readability."""
    cleaned = []
    for char in label.strip():
        if char.isalnum() or char in ("-", "_"):
            cleaned.append(char)
        elif char.isspace():
            cleaned.append("-")
    return "".join(cleaned).strip("-_")
