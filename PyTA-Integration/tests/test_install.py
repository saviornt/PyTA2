"""PyTA comes from the installed wheel, and this project uses only its public API."""

import re
import subprocess
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

import pyta

PROJECT_DIR = Path(__file__).resolve().parent.parent
SOURCE_TREE = PROJECT_DIR.parent / "python"  # PyTA's sources, never to be imported from here

# Private PyTA modules (the native extension included) and paths into PyTA's Rust crates. Built
# so that this file does not match its own patterns.
FORBIDDEN = re.compile(r"\bpyta\._(?!_)\w+|rust[/\\]crates")
SCANNED_SUFFIXES = {".py", ".sh", ".toml"}
SKIPPED_DIRS = {".venv", "dist", "__pycache__", ".pytest_cache", ".ruff_cache"}


def test_running_in_a_virtual_environment() -> None:
    assert sys.prefix != sys.base_prefix


def test_pyta_is_imported_from_site_packages() -> None:
    package_dir = Path(pyta.__file__).resolve().parent
    site_packages = Path(sysconfig.get_paths()["platlib"]).resolve()
    assert package_dir == site_packages / "pyta"
    assert not package_dir.is_relative_to(SOURCE_TREE.resolve())


def test_pyta_is_installed_from_a_wheel() -> None:
    distribution = metadata.distribution("pyta")
    direct_url = distribution.read_text("direct_url.json") or ""
    assert ".whl" in direct_url  # a wheel file, not an editable or source-tree install
    assert '"editable"' not in direct_url


def test_source_tree_is_not_on_the_path() -> None:
    entries = {Path(entry or ".").resolve() for entry in sys.path}
    assert SOURCE_TREE.resolve() not in entries
    assert PROJECT_DIR.parent.resolve() not in entries


def test_import_pyta_does_not_import_pandas() -> None:
    code = "import sys, pyta; print('pandas' in sys.modules)"
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=60
    )
    assert completed.stdout.strip() == "False"


def project_files() -> list[Path]:
    return sorted(
        path
        for path in PROJECT_DIR.rglob("*")
        if path.suffix in SCANNED_SUFFIXES
        and path.is_file()
        and not SKIPPED_DIRS.intersection(path.relative_to(PROJECT_DIR).parts)
    )


def test_scan_covers_the_project() -> None:
    names = {path.relative_to(PROJECT_DIR).as_posix() for path in project_files()}
    assert {"examples/batch.py", "tests/test_install.py", "scripts/setup.sh"} <= names


def test_no_private_modules_or_crate_paths() -> None:
    offenders = [
        f"{path.relative_to(PROJECT_DIR)}:{number}: {line.strip()}"
        for path in project_files()
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if FORBIDDEN.search(line)
    ]
    assert offenders == []
