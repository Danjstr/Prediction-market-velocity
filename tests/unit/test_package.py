"""Smoke tests for the pmv package skeleton."""

import importlib
import sys
from pathlib import Path


def test_python_version_is_3_13() -> None:
    assert sys.version_info[:2] == (3, 13)


def test_package_imports() -> None:
    module = importlib.import_module("pmv")
    assert module.__name__ == "pmv"


def test_package_is_marked_typed() -> None:
    module = importlib.import_module("pmv")
    assert module.__file__ is not None
    assert (Path(module.__file__).parent / "py.typed").is_file()
