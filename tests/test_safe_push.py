"""Pytest wrapper around ``tests/test_safe_push.sh``.

The actual scenarios — clean tree, leftover unstaged tracked-file edits
(the regression that took out the cron), concurrent push, untracked
artefacts — live in the bash file because they orchestrate real git
plumbing across two bare repos.  This wrapper just shells out so the
scenarios participate in the standard ``pytest tests/`` gate.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tests" / "test_safe_push.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_safe_push_scenarios():
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        pytest.fail(
            "safe_push.sh scenarios failed\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
