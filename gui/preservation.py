"""Byte-level audit of analysis code, inputs, historical outputs and evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/gui/CLEANUP_PRESERVED.json"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def paths():
    for folder in ("glassing", "configs", "docs/glassing", "data", "runs", "results"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                yield path
    for name in ("scout", "environment.scout.yml"):
        yield ROOT / name


def capture():
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths())}


def audit():
    expected = json.loads(MANIFEST.read_text())["sha256"]
    actual = capture()
    return [
        name
        for name in actual.keys() | expected.keys()
        if actual.get(name) != expected.get(name)
    ]


if __name__ == "__main__":
    if MANIFEST.exists():
        changed = audit()
        print(json.dumps(dict(changed=changed), indent=2))
        raise SystemExit(bool(changed))
    MANIFEST.write_text(
        json.dumps(
            dict(
                checkpoint="aeecf0b",
                scope="Analysis implementation, configurations, source data, historical runs/results, experimental evidence and hashed launchers. GUI source is excluded.",
                sha256=capture(),
            ),
            indent=2,
        )
        + "\n"
    )
    print(
        "Captured "
        + str(len(json.loads(MANIFEST.read_text())["sha256"]))
        + " protected files"
    )
