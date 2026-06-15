"""Model registry — persistent storage for trained ensembles + calibrators.

Each "registered round" is a directory under ``models/registry/<season>_round_<NN>/``
containing serialised model artefacts plus a JSON ``metadata.json``.  The
metadata file is intentionally small and human-readable so it can be committed
to git, while the binary artefacts (``*.joblib`` / ``*.pt``) are ignored by git
and treated as cacheable build output.

Why this exists
---------------
Today every CI run trains from scratch.  That blocks:
  - rollback to a previous round's model after a bad ship
  - shadow / A-B comparison of `production` vs `candidate` ensembles
  - drift attribution (was the regression in feature input or model fit?)

This module is the foundation.  Higher-level features (shadow models, drift
detection, auto-promotion) build on its ``save`` / ``load`` / ``latest`` API.

Public surface
--------------
::

    reg = ModelRegistry()                      # default root: models/registry/
    reg.save(season=2026, round_num=6,
             models={"gbr": gb, "xgb": xgb, "isotonic_win": iso_w, ...},
             metadata={"hyperparams": ..., "train_mae": 0.18, ...})
    reg.load(2026, 6)                          # → dict of the same shape
    reg.latest(2026)                           # → (round_num, metadata) | None
    reg.list_all()                             # → list[(season, round, metadata)]
    reg.exists(2026, 6)                        # → bool

Constraints
-----------
* Pure-additive — does not touch ``f1_prediction_utils.py``, ``leakage.py``,
  ``forward_eval.py`` here.  Callers opt in via ``registry_context`` kwarg or
  by calling ``ModelRegistry().save(...)`` themselves.
* Gated by ``F1_REGISTRY_ENABLED`` env var (default ``"1"``).  Setting it to
  ``"0"`` makes ``save()`` a logged no-op — required for tests and for hosts
  without write permission to ``models/registry/``.
* Atomic writes: serialises into a temp directory under the same parent and
  renames on success.  A crashed run never leaves a half-written round.
* Heavy deps (``joblib``, ``torch``) imported lazily so the module loads even
  if ``torch`` is absent.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LOGGER = logging.getLogger(__name__)

REGISTRY_ENV_VAR = "F1_REGISTRY_ENABLED"
DEFAULT_REGISTRY_ROOT = Path(__file__).resolve().parent / "registry"

# Filename prefixes/suffixes for typed dispatch.  Order matters: prefix matches
# are tried first so `lstm.pt` does not get joblib-loaded.
_TORCH_SUFFIX = ".pt"
_JOBLIB_SUFFIX = ".joblib"
_METADATA_FILE = "metadata.json"

_ROUND_DIR_RE = re.compile(r"^(?P<season>\d{4})_round_(?P<round>\d{2})$")


def registry_enabled() -> bool:
    """Honour the ``F1_REGISTRY_ENABLED`` env var.  Default: enabled."""
    return os.environ.get(REGISTRY_ENV_VAR, "1").strip() not in {"0", "false", "False", ""}


@dataclass
class ModelRegistry:
    """File-backed registry of trained model artefacts.

    Parameters
    ----------
    root
        Directory under which round subdirectories live.  Defaults to
        ``models/registry/`` relative to this module.  Override in tests.
    """

    root: Path = DEFAULT_REGISTRY_ROOT

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def save(
        self,
        season: int,
        round_num: int,
        models: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> Path | None:
        """Persist `models` + metadata under ``<root>/<season>_round_<NN>/``.

        Returns the directory path on success, ``None`` if the registry is
        disabled via env var.  Raises on actual write failures so the caller
        can decide how to react — at training time the typical wiring is::

            try:
                ModelRegistry().save(...)
            except Exception as exc:
                LOGGER.warning("registry save failed: %s", exc)
                # ... continue, don't crash the pipeline ...
        """
        if not registry_enabled():
            LOGGER.info("registry disabled via %s; skipping save", REGISTRY_ENV_VAR)
            return None

        round_dir = self._round_dir(season, round_num)
        # Stage writes into a sibling temp dir and rename on success — keeps
        # the registry consistent if the process is killed mid-save.
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{round_dir.name}_", dir=str(self.root)) as tmpdir:
            staging = Path(tmpdir)
            for name, obj in models.items():
                self._dump_artifact(staging / name, obj)
            full_metadata = self._enrich_metadata(season, round_num, models, metadata or {})
            with (staging / _METADATA_FILE).open("w", encoding="utf-8") as fh:
                json.dump(full_metadata, fh, indent=2, sort_keys=True, default=str)
            # Atomic-ish move into place.  If the destination already exists
            # we replace it (idempotent re-save).
            if round_dir.exists():
                shutil.rmtree(round_dir)
            shutil.move(str(staging), str(round_dir))
        LOGGER.info("registry: saved %s (%d artifacts)", round_dir.relative_to(self.root), len(models))
        return round_dir

    def load(self, season: int, round_num: int) -> dict[str, Any]:
        """Return the dict that was passed to ``save`` for this round.

        The returned dict contains the model objects keyed by their original
        names, plus a special ``"metadata"`` key with the saved metadata.
        Raises ``FileNotFoundError`` if the round was never registered.
        """
        round_dir = self._round_dir(season, round_num)
        if not round_dir.exists():
            raise FileNotFoundError(f"registry: round not found at {round_dir}")
        out: dict[str, Any] = {}
        for path in sorted(round_dir.iterdir()):
            if path.name == _METADATA_FILE:
                with path.open("r", encoding="utf-8") as fh:
                    out["metadata"] = json.load(fh)
                continue
            stem = path.stem
            out[stem] = self._load_artifact(path)
        return out

    def latest(self, season: int) -> tuple[int, dict[str, Any]] | None:
        """Highest-numbered round registered for a season, with metadata."""
        rounds = sorted(self._iter_season_rounds(season))
        if not rounds:
            return None
        last_round = rounds[-1]
        metadata_path = self._round_dir(season, last_round) / _METADATA_FILE
        if not metadata_path.exists():
            return last_round, {}
        with metadata_path.open("r", encoding="utf-8") as fh:
            return last_round, json.load(fh)

    def list_all(self) -> list[tuple[int, int, dict[str, Any]]]:
        """Return ``(season, round, metadata)`` for every registered round.

        Sorted by season, then round.  Missing/corrupt ``metadata.json`` is
        surfaced as an empty dict rather than raised — the caller can decide
        what to do with an artefact-only round.
        """
        out: list[tuple[int, int, dict[str, Any]]] = []
        if not self.root.exists():
            return out
        for child in sorted(self.root.iterdir()):
            match = _ROUND_DIR_RE.match(child.name)
            if not match:
                continue
            season = int(match.group("season"))
            round_num = int(match.group("round"))
            metadata_path = child / _METADATA_FILE
            metadata: dict[str, Any] = {}
            if metadata_path.exists():
                try:
                    with metadata_path.open("r", encoding="utf-8") as fh:
                        metadata = json.load(fh)
                except (OSError, json.JSONDecodeError) as exc:
                    LOGGER.warning("registry: bad metadata at %s: %s", metadata_path, exc)
            out.append((season, round_num, metadata))
        out.sort(key=lambda row: (row[0], row[1]))
        return out

    def exists(self, season: int, round_num: int) -> bool:
        return self._round_dir(season, round_num).exists()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _round_dir(self, season: int, round_num: int) -> Path:
        if season < 1950 or season > 2100:
            raise ValueError(f"season out of expected range: {season!r}")
        # 1..30 covers any real F1 calendar; 31..99 is reserved for sentinel
        # entries that aren't tied to a specific weekend (e.g. the race-pace
        # ensemble trained on multi-season data under round=99, see
        # train_race_pace.py::RACE_PACE_REGISTRY_ROUND).
        if round_num < 1 or round_num > 99:
            raise ValueError(f"round_num out of expected range: {round_num!r}")
        return self.root / f"{season:04d}_round_{round_num:02d}"

    def _iter_season_rounds(self, season: int) -> Iterable[int]:
        if not self.root.exists():
            return []
        prefix = f"{season:04d}_round_"
        result: list[int] = []
        for child in self.root.iterdir():
            if not child.name.startswith(prefix):
                continue
            match = _ROUND_DIR_RE.match(child.name)
            if match:
                result.append(int(match.group("round")))
        return result

    @staticmethod
    def _dump_artifact(path: Path, obj: Any) -> None:
        """Serialise `obj` to `path`, picking the right format by type."""
        # Lazy imports so the module loads without torch.
        if _looks_like_torch_module(obj):
            torch = _import_torch_or_raise()
            # We save the state_dict, not the full module — smaller and
            # avoids pickle-of-class-definition compatibility issues.
            torch.save(obj.state_dict(), str(path.with_suffix(_TORCH_SUFFIX)))
            return
        import joblib  # bundled with scikit-learn

        joblib.dump(obj, str(path.with_suffix(_JOBLIB_SUFFIX)))

    @staticmethod
    def _load_artifact(path: Path) -> Any:
        if path.suffix == _TORCH_SUFFIX:
            torch = _import_torch_or_raise()
            return torch.load(str(path), map_location="cpu", weights_only=True)
        if path.suffix == _JOBLIB_SUFFIX:
            import joblib

            return joblib.load(str(path))
        raise ValueError(f"registry: unsupported artifact extension {path.suffix!r}")

    @staticmethod
    def _enrich_metadata(
        season: int,
        round_num: int,
        models: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Attach the standard provenance fields callers shouldn't have to."""
        enriched: dict[str, Any] = dict(metadata)
        enriched.setdefault("season", season)
        enriched.setdefault("round", round_num)
        enriched.setdefault("artifacts", sorted(models.keys()))
        enriched.setdefault("savedAt", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        enriched.setdefault("pythonVersion", _python_version())
        enriched.setdefault("gitSha", _git_sha_or_unknown())
        return enriched


# --------------------------------------------------------------------------- #
# Helpers (kept private so callers don't depend on internals)
# --------------------------------------------------------------------------- #


def _looks_like_torch_module(obj: Any) -> bool:
    """True if `obj` has the duck-type signature of an nn.Module.

    We avoid importing torch at module load.  This check is intentionally
    structural — anything with ``state_dict()`` + ``parameters()`` qualifies.
    """
    return callable(getattr(obj, "state_dict", None)) and callable(
        getattr(obj, "parameters", None)
    )


def _import_torch_or_raise():
    try:
        import torch  # noqa: PLC0415 — intentional lazy import
    except ImportError as exc:
        raise RuntimeError(
            "registry: artefact requires torch but torch is not installed"
        ) from exc
    return torch


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _git_sha_or_unknown() -> str:
    """Return the current git HEAD sha, or 'unknown' if not a git repo."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parent.parent),
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode("utf-8").strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "unknown"
