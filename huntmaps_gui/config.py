"""Application paths shared by request handlers, tests and child workers."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    source_dir: Path = PROJECT
    state_dir: Path = PROJECT / ".gui"
    workspace: Path = PROJECT
    display_budget_bytes: int = 2048 * 1024 * 1024

    def __post_init__(self):
        for field in ("source_dir", "state_dir", "workspace"):
            object.__setattr__(self, field, Path(getattr(self, field)).resolve())
        if self.display_budget_bytes < 0:
            raise ValueError("Display cache budget must be nonnegative")

    @classmethod
    def from_env(cls):
        return cls(
            Path(os.environ.get("HUNTMAPS_SOURCE_DIR", PROJECT)),
            Path(os.environ.get("HUNTMAPS_STATE_DIR", PROJECT / ".gui")),
            Path(os.environ.get("HUNTMAPS_WORKSPACE", PROJECT)),
            int(os.environ.get("HUNTMAPS_DISPLAY_BUDGET_MB", "2048")) * 1024 * 1024,
        )

    def environment(self):
        return dict(
            HUNTMAPS_SOURCE_DIR=str(self.source_dir),
            HUNTMAPS_STATE_DIR=str(self.state_dir),
            HUNTMAPS_WORKSPACE=str(self.workspace),
            HUNTMAPS_DISPLAY_BUDGET_MB=str(self.display_budget_bytes // (1024 * 1024)),
        )


_current = ContextVar("huntmaps_config", default=None)


def current():
    return _current.get() or AppConfig.from_env()


@contextmanager
def configured(config):
    token = _current.set(config)
    try:
        yield config
    finally:
        _current.reset(token)


class ConfigPath(os.PathLike):
    """Resolve at use time, so imported path handles never capture test globals."""

    def __init__(self, field, *parts):
        self.field, self.parts = field, parts

    def resolve(self):
        return getattr(current(), self.field).joinpath(*self.parts)

    def __fspath__(self):
        return str(self.resolve())

    def __str__(self):
        return str(self.resolve())

    def __truediv__(self, part):
        return self.resolve() / part

    def __getattr__(self, name):
        return getattr(self.resolve(), name)


SOURCE = ConfigPath("source_dir")
STATE = ConfigPath("state_dir")
WORKSPACE = ConfigPath("workspace")
