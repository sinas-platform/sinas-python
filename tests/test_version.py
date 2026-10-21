"""sinas.__version__ must match the version in pyproject.toml."""

import pathlib
import re

import sinas


def test_version_matches_pyproject():
    text = (pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    project = re.search(r"^\[project\][ \t]*$(.*?)(?=^\[|\Z)", text, re.MULTILINE | re.DOTALL)
    assert project is not None
    version = re.search(r"""^version\s*=\s*["']([^"']+)["']""", project.group(1), re.MULTILINE)
    assert version is not None
    assert sinas.__version__ == version.group(1)
