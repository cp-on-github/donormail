import shutil
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Copy the examples into a temporary working directory."""

    for example in ("basic", "quickbooks"):
        shutil.copytree(
            EXAMPLES / example,
            tmp_path / example,
            ignore=shutil.ignore_patterns("output"),
        )
    monkeypatch.chdir(tmp_path)
    return tmp_path
