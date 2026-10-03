"""GUI-only acquisition instrumentation; historical CLI Fetcher remains unchanged."""

import sys
import urllib.request
from .downloads import check_space
from .progress import received, flush_download, emit
from glassing.acquire import Fetcher

_original_init = Fetcher.__init__
_original_get = Fetcher.get


def initialize(self, root, budget):
    _original_init(self, root, budget)
    # A reviewed GUI allowance covers new transfer, not already verified cached files.
    self.budget = budget


def get(self, name, url, **metadata):
    original = urllib.request.urlopen

    def open_response(*args, **kwargs):
        response = original(*args, **kwargs)
        read = response.read

        def tracked(size=-1):
            check_space(self.root, max(0, size))
            block = read(size)
            check_space(self.root, len(block))
            received(len(block), url)
            return block

        response.read = tracked
        return response

    urllib.request.urlopen = open_response
    try:
        result = _original_get(self, name, url, **metadata)
        return result
    finally:
        flush_download()
        urllib.request.urlopen = original


def main():
    Fetcher.__init__ = initialize
    Fetcher.get = get
    from glassing import owner_data

    original_provision = owner_data.provision

    def provision(*args, **kwargs):
        ready = original_provision(*args, **kwargs)
        flush_download()
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
            from . import search, search_worker
            from .storage import read_json

            config = read_json(Path(path).parent / "scouting.json", {})
            if config.get("search"):
                value.update(
                    {
                        str(Path(module.__file__)): owner.sha(module.__file__)
                        for module in [search, search_worker]
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
