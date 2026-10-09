"""Verify or reconstruct the unchanged records from reviewed PR18 head e01f36e."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(evidence: Path, repo: Path, reference: str | None) -> dict[str, bytes]:
    manifest = json.loads((evidence / "evidence-manifest.json").read_text())
    require(manifest["schemaVersion"] == 1, "Unsupported manifest version")
    rows = manifest["files"]
    require(len(rows) == manifest["originalFiles"], "Original file count differs")
    expected = {}
    for name, storage, size, sha in rows:
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts, f"Unsafe path: {name}")
        require(name not in expected, f"Duplicate manifest member: {name}")
        require(isinstance(size, int) and size >= 0, f"Invalid size: {name}")
        require(re.fullmatch(r"[a-f0-9]{64}", sha) is not None, f"Invalid hash: {name}")
        expected[name] = (storage, size, sha)
    require(sum(row[2] for row in rows) == manifest["originalBytes"], "Byte count differs")
    payloads = {}

    def accept(name: str, storage: str, data: bytes) -> None:
        require(name in expected and name not in payloads, f"Unexpected member: {name}")
        location, size, sha = expected[name]
        require(location == storage, f"Storage differs: {name}")
        require(len(data) == size and digest(data) == sha, f"Content differs: {name}")
        payloads[name] = data

    for name, (storage, _, _) in expected.items():
        if storage == "retained":
            accept(name, storage, (evidence / name).read_bytes())
    archive_names = set()
    for record in manifest["archives"]:
        name = record["file"]
        require(name not in archive_names and Path(name).name == name, "Invalid archive name")
        archive_names.add(name)
        data = (evidence / name).read_bytes()
        require(
            len(data) == record["bytes"] and digest(data) == record["sha256"],
            f"Archive hash differs: {name}",
        )
        count = total = 0
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                require(member.isfile() and not member.linkname, "Non-regular archive member")
                require(member.name in expected, f"Unlisted archive member: {member.name}")
                require(member.size == expected[member.name][1], "Archive member size differs")
                stream = archive.extractfile(member)
                require(stream is not None, "Unreadable archive member")
                content = stream.read()
                accept(member.name, name, content)
                count += 1
                total += len(content)
        require(
            count == record["members"] and total == record["payloadBytes"],
            f"Archive inventory differs: {name}",
        )
    require(set(payloads) == set(expected), "Original records are missing")

    summary = json.loads((evidence / "browser-summary.json").read_text())
    require(summary["reviewedCodeCommit"] == manifest["sourceCommit"], "Summary commit differs")
    require(
        summary["allSites"] == json.loads(payloads["browser-sites/classification.json"]),
        "Browser classification summary differs",
    )
    for section, path, key, hashes in [
        ("energy", "browser-energy/browser-qa.json", "variants", "sourceHashes"),
        ("freshness", "browser-freshness/browser-qa.json", "cases", "hashes"),
    ]:
        raw = json.loads(payloads[path])
        require(summary[section]["cases"] == len(raw[key]), f"{section} case count differs")
        require(
            summary[section]["passed"] == sum(case.get("passed", False) for case in raw[key]),
            f"{section} passed count differs",
        )
        require(summary[section]["sourceHashes"] == raw[hashes], f"{section} hashes differ")
    raw = json.loads(payloads["browser-hydration/summary.json"])
    require(summary["hydration"]["cases"] == len(raw["results"]), "Hydration count differs")
    require(
        summary["hydration"]["pageErrors"] == sum(len(case["errors"]) for case in raw["results"]),
        "Hydration errors differ",
    )
    require(summary["hydration"]["htmlHashes"] == raw["files"], "Hydration HTML hashes differ")

    trees = json.loads((evidence / "tested-source-trees.json").read_text())
    require(trees["reviewedCommit"] == manifest["sourceCommit"], "Reviewed commits differ")
    for name, expected_tree in trees["gitTrees"].items():
        actual = subprocess.check_output(
            ["git", "rev-parse", f"HEAD:{name}"], cwd=repo, text=True
        ).strip()
        require(actual == expected_tree, f"Tested source tree changed: {name}")
        subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", name],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "diff", "--cached", "--exit-code", "HEAD", "--", name],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        )
    inputs = json.loads((evidence / "check-inputs.json").read_text())
    for name, sha in inputs.items():
        require(digest((repo / name).read_bytes()) == sha, f"Locked input changed: {name}")
    for name, sha in json.loads((evidence / "qa-runner-hashes.json").read_text()).items():
        require(digest((repo / name).read_bytes()) == sha, f"QA runner changed: {name}")

    if reference:
        require(re.fullmatch(r"[a-f0-9]{40}", reference) is not None, "Use a full commit SHA")
        require(reference == manifest["sourceCommit"], "Reference is not the reviewed head")
        for name, expected_tree in trees["gitTrees"].items():
            original_tree = subprocess.check_output(
                ["git", "rev-parse", f"{reference}:{name}"], cwd=repo, text=True
            ).strip()
            require(original_tree == expected_tree, f"Reviewed source tree differs: {name}")
        prefix = manifest["sourceDirectory"]
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", reference, "--", prefix], cwd=repo, text=True
        ).splitlines()
        require(
            {path.removeprefix(prefix + "/") for path in paths} == set(payloads),
            "Reviewed Git inventory differs",
        )
        for name, data in payloads.items():
            original = subprocess.check_output(
                ["git", "show", f"{reference}:{prefix}/{name}"], cwd=repo
            )
            require(data == original, f"Reviewed Git bytes differ: {name}")
    return payloads


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--reference", help="Compare every original file to this reviewed Git SHA")
    parser.add_argument(
        "--extract", type=Path, help="Reconstruct all original records in a new directory"
    )
    parser.add_argument(
        "--repack", type=Path, help="Recreate deterministic archives in a new directory"
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    try:
        payloads = verify(args.evidence_dir.resolve(), repo, args.reference)
        if args.extract:
            destination = args.extract.resolve()
            require(not destination.is_relative_to(repo), "Extract outside the source repository")
            require(not destination.exists(), "Extraction directory must be new")
            destination.mkdir(parents=True)
            for name, data in payloads.items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        if args.repack:
            destination = args.repack.resolve()
            require(not destination.is_relative_to(repo), "Repack outside the source repository")
            require(not destination.exists(), "Repack directory must be new")
            destination.mkdir(parents=True)
            manifest = json.loads((args.evidence_dir / "evidence-manifest.json").read_text())
            for record in manifest["archives"]:
                raw = io.BytesIO()
                with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    for name, storage, _, _ in manifest["files"]:
                        if storage != record["file"]:
                            continue
                        info = tarfile.TarInfo(name)
                        info.size = len(payloads[name])
                        info.mode = 0o644
                        info.mtime = info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        archive.addfile(info, io.BytesIO(payloads[name]))
                compressed = io.BytesIO()
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9
                ) as stream:
                    stream.write(raw.getvalue())
                data = compressed.getvalue()
                require(digest(data) == record["sha256"], "Repacked archive hash differs")
                (destination / record["file"]).write_bytes(data)
        print(
            json.dumps(
                {
                    "verifiedOriginalFiles": len(payloads),
                    "verifiedOriginalBytes": sum(len(data) for data in payloads.values()),
                    "reference": args.reference,
                    "testedSourceTreesUnchanged": True,
                    "extractedTo": str(args.extract) if args.extract else None,
                    "repackedTo": str(args.repack) if args.repack else None,
                }
            )
        )
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        parser.exit(1, f"Evidence verification failed: {error}\n")


if __name__ == "__main__":
    main()
