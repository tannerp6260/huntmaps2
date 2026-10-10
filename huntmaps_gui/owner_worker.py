"""GUI-only acquisition instrumentation; historical CLI Fetcher remains unchanged."""

import sys
import datetime
import time
from pathlib import Path
import urllib.request
from urllib.error import HTTPError
from .downloads import check_space
from .progress import received, flush_download, emit
from .storage import locked, read_json, write as atomic_write
from .acquisition import (
    ProviderResponseError,
    label,
    retain_rejected,
    validate,
    validating,
)
from glassing.acquire import Fetcher, digest

_original_init = Fetcher.__init__


def initialize(self, root, budget):
    _original_init(self, root, budget)
    # A reviewed GUI allowance covers new transfer, not already verified cached files.
    self.budget = budget
    import os
    from .storage import read_json

    if os.environ.get("HUNTMAPS_TRANSFER_LEDGER"):
        ledger = read_json(os.environ["HUNTMAPS_TRANSFER_LEDGER"], {})
        self.budget = min(
            budget, max(0, ledger["ceiling_bytes"] - ledger["received_bytes"])
        )


def get(self, name, url, **metadata):
    """Publish only validated responses, with the original transfer and source guards."""
    try:
        with locked(self.manifest_path):
            self.entries = read_json(self.manifest_path, {})
            path = self.root / name
            if path.exists():
                old = self.entries.get(name)
                if not old or old["url"] != url or old["sha256"] != digest(path):
                    raise ValueError(
                        f"Unverified or changed input: {path}; use a new input directory"
                    )
                try:
                    validate(path, name, metadata)
                except ProviderResponseError as error:
                    if digest(path) != old["sha256"]:
                        raise ValueError(
                            f"Changed input during source validation: {path}"
                        ) from error
                    retain_rejected(self.root, path, name, old, error)
                    self.entries.pop(name)
                    atomic_write(self.manifest_path, self.entries)
                else:
                    if digest(path) != old["sha256"]:
                        raise ValueError(
                            f"Changed input during source validation: {path}"
                        )
                    return path
            print(
                f"STAGE Downloading and validating {label(name, metadata)}", flush=True
            )
            partial = path.with_suffix(path.suffix + ".partial")
            # Preserve interrupted bytes before retrying the same reviewed request.
            if partial.exists():
                retain_rejected(
                    self.root,
                    partial,
                    name,
                    dict(url=url, **metadata),
                    "Interrupted transfer; not a validated source",
                )
            request = urllib.request.Request(
                url, headers={"User-Agent": "glassing-terrain-experiment/0.1"}
            )
            http_error = None
            try:
                response = urllib.request.urlopen(request, timeout=60)
            except HTTPError as error:
                response, http_error = error, error.code
            with response, partial.open("wb") as stream:
                length = response.headers.get("Content-Length")
                if length and self.used + int(length) > self.budget:
                    raise ValueError("Download budget exceeded before transfer")
                while True:
                    check_space(self.root, 1024 * 1024)
                    block = response.read(1024 * 1024)
                    self.used += len(block)
                    received(len(block), url)
                    if self.used > self.budget:
                        raise ValueError(
                            "Download budget exceeded; partial file is not accepted"
                        )
                    check_space(self.root, len(block))
                    if not block:
                        break
                    stream.write(block)
            entry = dict(
                url=url,
                sha256=digest(partial),
                bytes=partial.stat().st_size,
                elapsed_since_fetcher_start_s=time.monotonic() - self.started,
                retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                **metadata,
            )
            try:
                validate(partial, name, metadata)
                if http_error:
                    raise ProviderResponseError(
                        f"{label(name, metadata)} returned HTTP {http_error}"
                    )
            except ProviderResponseError as error:
                retain_rejected(self.root, partial, name, entry, error)
                raise
            if digest(partial) != entry["sha256"]:
                raise ValueError(f"Changed input during download validation: {partial}")
            partial.replace(path)
            self.entries[name] = entry
            atomic_write(self.manifest_path, self.entries)
            return path
    finally:
        flush_download()


def main():
    Fetcher.__init__ = initialize
    Fetcher.get = get
    from glassing import owner_data
    from .source_reuse import cached

    original_cached = owner_data.cached
    owner_data.cached = lambda config, inputs: cached(config, inputs, original_cached)

    original_provision = owner_data.provision

    def provision(*args, **kwargs):
        with validating(args[0], args[1]):
            ready = original_provision(*args, **kwargs)
        flush_download()
        if not ready:
            errors = read_json(Path(args[2]) / "acquisition.json", {}).get("errors", [])
            if errors:
                print(
                    "SCOUT: Approved source acquisition failed: " + "; ".join(errors),
                    flush=True,
                )
        if ready and "run" in sys.argv:
            emit("processing", "Evaluating terrain and preparing outputs", force=True)
        return ready

    owner_data.provision = provision
    import subprocess

    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if isinstance(command, list) and command[1:4] == [
            "-m",
            "glassing.transfer",
            "all",
        ]:
            from .storage import read_json

            config = command[command.index("--config") + 1]
            if read_json(config, {}).get("search"):
                command = [
                    sys.executable,
                    "-m",
                    "huntmaps_gui.search_worker",
                    "--config",
                    config,
                ]
        return original_run(command, *args, **kwargs)

    subprocess.run = run
    from glassing import owner

    original_write = owner.write

    def write(path, value):
        from pathlib import Path

        if Path(path).name == "manifest.json":
            from . import (
                search,
                search_worker,
                sampling,
                evaluation,
                storage,
                acquisition,
                source_reuse,
            )
            from .storage import read_json

            config = read_json(Path(path).parent / "scouting.json", {})
            if config.get("search"):
                value.update(
                    {
                        str(Path(module.__file__)): owner.sha(module.__file__)
                        for module in [
                            search,
                            search_worker,
                            sampling,
                            evaluation,
                            storage,
                            search.target_filters,
                            acquisition,
                            source_reuse,
                        ]
                    }
                )
        return original_write(path, value)

    owner.write = write
    from glassing import owner_results

    original_handoff = owner_results.handoff

    def handoff(config, root):
        original_handoff(config, root)
        if config.get("search"):
            from .search import guidance

            guidance(config, root)

    owner_results.handoff = handoff
    return owner.main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError) as error:
        print("SCOUT:", error, file=sys.stderr)
        sys.exit(2)
