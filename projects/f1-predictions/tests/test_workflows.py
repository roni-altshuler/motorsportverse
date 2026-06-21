"""Static checks on GitHub Actions workflows.

These tests are deliberately narrow — they pin down the invariants that
have historically broken the cron, not the full YAML shape:

* Workflow YAML parses (no accidental tab / indentation regressions).
* Every workflow that commits + pushes to ``main`` routes its push
  through ``.github/scripts/safe_push.sh``.  Direct ``git rebase
  origin/main`` + ``git push`` loops in workflows were the source of
  the 2026-05-23 cron failure: a tracked file modified by the pipeline
  but not staged by the commit step aborted the rebase pre-check.
  Routing through safe_push.sh forces the auto-stash protection.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
SAFE_PUSH = REPO_ROOT / ".github" / "scripts" / "safe_push.sh"


def _iter_steps(workflow: dict):
    for job in (workflow.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            yield step


def _step_scripts(workflow: dict) -> list[str]:
    return [step["run"] for step in _iter_steps(workflow) if isinstance(step.get("run"), str)]


def test_safe_push_script_exists_and_executable():
    assert SAFE_PUSH.is_file(), "safe_push.sh is missing"
    # Octal 0o100 == owner-execute bit
    assert SAFE_PUSH.stat().st_mode & 0o111, "safe_push.sh is not executable"


@pytest.mark.parametrize("path", sorted(WORKFLOWS_DIR.glob("*.yml")))
def test_workflow_yaml_parses(path: Path):
    with path.open() as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict), f"{path.name} did not parse as a mapping"
    # PyYAML maps the `on:` key to the Python bool True because YAML 1.1
    # treats `on` as a truthy keyword.  Either form is fine here; we only
    # care that the workflow has triggers and at least one job.
    assert (True in data) or ("on" in data), f"{path.name} missing triggers"
    assert data.get("jobs"), f"{path.name} has no jobs"


def test_cron_workflows_route_pushes_through_safe_push():
    """update_predictions.yml and backfill_history.yml both commit + push.

    The regression was a hand-rolled retry loop that did not handle
    leftover unstaged changes.  Make sure those scripts now invoke
    safe_push.sh instead.
    """
    targets = ["update_predictions.yml", "backfill_history.yml"]
    for name in targets:
        path = WORKFLOWS_DIR / name
        with path.open() as fh:
            workflow = yaml.safe_load(fh)
        scripts = _step_scripts(workflow)
        joined = "\n".join(scripts)
        # The committing step must invoke safe_push.sh — that is what
        # provides the auto-stash + retry behaviour.
        assert ".github/scripts/safe_push.sh" in joined, (
            f"{name} no longer routes pushes through safe_push.sh; "
            "this re-opens the 2026-05-23 rebase regression."
        )
        # And it must not have re-grown a bare ``git rebase origin/main``
        # without first stashing — that is the exact failure mode.
        if "git rebase origin/main" in joined:
            assert "--autostash" in joined or "stash" in joined, (
                f"{name} runs `git rebase origin/main` without --autostash "
                "or an explicit stash — leftover unstaged pipeline output "
                "will abort the rebase pre-check."
            )


def test_update_predictions_stages_registry_metadata():
    """The pipeline overwrites ``models/registry/*/metadata.json`` every run.

    CLAUDE.md mandates that those JSONs ARE committed (only the binaries
    are gitignored).  If the commit step stops staging them, they land
    as unstaged tracked-file changes after the curated commit — which
    historically broke the subsequent rebase.  safe_push.sh now stashes
    around that, but staging them is still the correct intent.
    """
    path = WORKFLOWS_DIR / "update_predictions.yml"
    with path.open() as fh:
        workflow = yaml.safe_load(fh)
    scripts = "\n".join(_step_scripts(workflow))
    assert "git add -f models/registry/" in scripts, (
        "update_predictions.yml stopped staging models/registry/. "
        "Per CLAUDE.md the per-round metadata.json files are tracked, "
        "and leaving them unstaged after the curated commit breaks rebase."
    )
