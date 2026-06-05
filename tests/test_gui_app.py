import os
import subprocess
import sys

import pytest


def test_app_can_be_created_without_starting_run():
    script = """
import tkinter as tk
from tc1d.gui.app import create_app

root = tk.Tk()
root.withdraw()
app = create_app(root)
assert app.run_type_var.get() == "forward"
assert app.process is None
root.destroy()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    if result.returncode < 0 or "no display" in result.stderr.lower():
        pytest.skip(f"Tk cannot create a window in this environment: {result.stderr}")
    assert result.returncode == 0, result.stderr
