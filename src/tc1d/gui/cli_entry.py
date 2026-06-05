"""Source-tree friendly Tc1D CLI entry point for GUI subprocesses.

The GUI still runs the existing ``tc1d.tc1d_cli`` module. This wrapper only
patches version lookup so the CLI can run from an unpacked source tree that has
not been installed as a package.
"""

from __future__ import annotations

import importlib.metadata

from tc1d import __version__


def _patch_tc1d_version_lookup() -> None:
    """Let tc1d_cli run from an uninstalled source tree."""
    original_version = importlib.metadata.version

    def version_with_source_tree_fallback(package_name: str) -> str:
        if package_name == "tc1d":
            try:
                return original_version(package_name)
            except importlib.metadata.PackageNotFoundError:
                # Keep --version and parser setup working in source-tree runs.
                return __version__
        return original_version(package_name)

    importlib.metadata.version = version_with_source_tree_fallback


def main() -> None:
    """Run the existing Tc1D CLI after applying the local metadata fallback."""
    _patch_tc1d_version_lookup()
    from tc1d.tc1d_cli import main as tc1d_cli_main

    tc1d_cli_main()


if __name__ == "__main__":
    main()
