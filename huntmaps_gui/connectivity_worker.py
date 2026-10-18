"""Bounded, cancellable screen subprocess; no source acquisition or route search."""

import argparse
import resource
import signal
from .connectivity import calculate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("token")
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
    signal.alarm(900)
    calculate(args.run, args.token)


if __name__ == "__main__":
    main()
