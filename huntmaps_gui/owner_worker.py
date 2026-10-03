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
    from glassing.owner import main as owner_main

    return owner_main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError) as error:
        print("SCOUT:", error, file=sys.stderr)
        sys.exit(2)
