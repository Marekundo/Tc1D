# Tc1D Desktop GUI

This GUI is a Tkinter front end for preparing and running Tc1D configs. It does
not replace the scientific model code. The GUI collects settings, writes a YAML
file, and launches the existing Tc1D CLI in a subprocess.

> **Platform support:** The GUI has been tested only on macOS. Its run plumbing
> assumes a POSIX environment: it exposes locally built Tc_core executables
> through a temporary no-space path (recompiling `ketch_aft` with `gcc` when it
> can, otherwise copying the existing binary) and prefers `.venv/bin/python`. It
> is not expected to work as-is on Windows.

## What It Does

- Presents Tc1D settings in guided tabs.
- Imports and exports the same YAML-style config used by the CLI.
- Supports `forward`, `batch`, `na`, and `mcmc` run types.
- Writes each run into a timestamped output directory.
- Streams stdout and stderr into the Run log tab.
- Lists generated `csv/` and `png/` outputs after the run finishes.
- Allows a running subprocess to be cancelled.

## What It Does Not Do

- It does not edit Tc1D's scientific model functions.
- It does not inspect live internal model arrays.
- It does not replace the `RDAAM_He` or `ketch_aft` executables from Tc_core.

## Running It From A Source Checkout

From the repository root:

```bash
PYTHONPATH=src python3 -m tc1d.gui.app
```

If the package is installed with the GUI entry point available:

```bash
tc1d-gui
```

The model subprocess prefers `.venv/bin/python` when that file exists. This is
useful when the GUI itself is launched with a system Python, but Tc1D's
scientific dependencies are installed in a local virtual environment.

## Required External Executables

Tc1D age calculations require the Tc_core executables:

- `RDAAM_He`
- `ketch_aft`

The GUI checks for these before launching a run unless age calculation is
disabled. If local copies exist under `src/RDAAM_He` or `src/ketch_aft`, the GUI
adds those directories to `PATH`. It also exposes local executables through a
temporary no-space path so Tc1D can run correctly from repository paths that
contain spaces.

## How A Run Works

1. The form is converted into a nested config dictionary.
2. The config is normalized so `run_type`, `batch_mode`, and `inverse_mode`
   agree with one another.
3. The config is validated for GUI-level issues, such as missing multi-stage
   erosion rows for erosion type `0`.
4. A timestamped run directory is created under the selected output root.
5. The generated YAML is written as `tc1d_gui_input.yaml`.
6. The GUI runs:

   ```bash
   python -m tc1d.gui.cli_entry --input-file tc1d_gui_input.yaml
   ```

7. `tc1d.gui.cli_entry` applies a package-version fallback for source-tree
   runs, then calls the existing `tc1d.tc1d_cli.main()`.
8. Tc1D writes its normal `csv/` and `png/` outputs into the run directory.

## YAML Import And Export

The YAML tab is a round-trip view of the current form state:

- **Refresh YAML** rebuilds the preview from the form.
- **Apply YAML** parses the preview and pushes it back into the form.
- **Import YAML** loads a file from disk.
- **Export YAML** writes the current form state to disk.

For inverse runs, parameters that are ranges should be entered as two values,
for example:

```text
0.1, 5.0
```

The GUI serializes that as a YAML list:

```yaml
duration_myr: [0.1, 5.0]
```

## Results Tab

After a run finishes, the Results tab lists generated PNG and CSV files. PNG
files are previewed as images, and CSV files are previewed as text. The GUI only
shows files written by Tc1D; it does not promise access to intermediate arrays
inside the running model.

## Development Notes

The GUI code lives under `src/tc1d/gui/`:

- `app.py`: Tkinter widgets, form state, YAML preview, run log, results preview.
- `config.py`: defaults, YAML parsing/serialization, validation helpers.
- `runner.py`: run directory creation, subprocess command/environment setup.
- `cli_entry.py`: source-tree-friendly wrapper around the existing CLI.

Focused GUI tests live in:

- `tests/test_gui_app.py`
- `tests/test_gui_config.py`
- `tests/test_gui_runner.py`

Run them with:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_gui_app.py tests/test_gui_config.py tests/test_gui_runner.py
```

## Files To Keep Out Of Commits

Local run folders and caches are intentionally ignored:

- `tc1d_gui_runs/`
- `.tc1d_gui_cache/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- locally built `RDAAM_He`, `RDAAM.o`, and `ketch_aft` binaries
