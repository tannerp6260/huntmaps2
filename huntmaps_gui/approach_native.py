"""Optional local C++ acceleration with an exact Python fallback.

The Ubuntu compiler is used only for a small project-owned shared library. Builds
are locked, atomic and content-keyed. No packages or system paths are modified.
"""

from collections.abc import Mapping
import ctypes
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import numpy as np
from glassing.acquire import digest
from .config import STATE
from .storage import locked, write, read_json

FLAGS = (
    "-std=c++17",
    "-O2",
    "-shared",
    "-fPIC",
    "-fno-fast-math",
    "-ffp-contract=off",
    "-fno-builtin-pow",
)


@lru_cache(maxsize=16)
def _load(path, identity):
    library = ctypes.CDLL(path)
    pointer = ctypes.c_void_p
    library.hm_start.argtypes = (
        [ctypes.c_int, ctypes.c_int]
        + [ctypes.c_double] * 4
        + [pointer] * 7
        + [ctypes.c_int64, ctypes.c_double, pointer, pointer]
    )
    library.hm_start.restype = pointer
    library.hm_step.argtypes = [pointer, ctypes.c_int]
    library.hm_step.restype = ctypes.c_int
    library.hm_stop.argtypes = [pointer]
    library.hm_stop.restype = None
    return library


def library():
    compiler = shutil.which("c++")
    if compiler is None:
        return None
    source = Path(__file__).with_name("approach_dijkstra.cpp")
    key = hashlib.sha256(
        (digest(source) + repr(FLAGS) + platform.machine()).encode()
    ).hexdigest()[:24]
    folder = STATE / "native" / key
    binary = folder / "dijkstra.so"
    with locked(folder / "build"):
        if binary.exists():
            expected = read_json(folder / "binary.json", {}).get("sha256")
            if digest(binary) != expected:
                raise ValueError(
                    "Native approach cache changed; retain it for diagnosis and remove this regenerable cache before retrying"
                )
        else:
            with tempfile.TemporaryDirectory(dir=folder) as temporary:
                output = Path(temporary) / "dijkstra.so"
                try:
                    result = subprocess.run(
                        [compiler, *FLAGS, str(source), "-o", str(output)],
                        capture_output=True,
                        timeout=45,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    return None
                if result.returncode:
                    return None
                h = digest(output)
                # A failed build never leaves a published library.
                output.replace(binary)
                write(
                    folder / "binary.json",
                    dict(sha256=h, source_sha256=digest(source), flags=FLAGS),
                )
        return _load(str(binary), digest(binary))


class Cells(Mapping):
    """Dense internal arrays with the previous reachable-cell mapping interface."""

    def __init__(self, distances, successors=None):
        self.distances = distances
        self.successors = successors

    def __getitem__(self, cell):
        r, c = cell
        if not (
            0 <= r < self.distances.shape[0] and 0 <= c < self.distances.shape[1]
        ) or not np.isfinite(self.distances[r, c]):
            raise KeyError(cell)
        if self.successors is None:
            return float(self.distances[r, c])
        n = int(self.successors[r, c])
        return None if n < 0 else divmod(n, self.distances.shape[1])

    def __iter__(self):
        for cell in np.argwhere(np.isfinite(self.distances)):
            yield tuple(int(v) for v in cell)

    def __len__(self):
        return int(np.isfinite(self.distances).sum())


def search(grid, end, initial, weights):
    # The original NumPy float32 subtraction/addition rounds before float().
    # Preserve that path, and support installations without a local compiler.
    arrays = [grid.dem, grid.slope, grid.penalty_tree, grid.penalty_shrub]
    if any(a.dtype != np.float64 for a in arrays):
        return None
    native = library()
    if native is None:
        return None
    arrays = [np.ascontiguousarray(a) for a in arrays]
    valid = np.ascontiguousarray(grid.valid, dtype=np.uint8)
    edges = np.ascontiguousarray(grid.edge_valid, dtype=np.uint8)
    w = np.array(
        [weights[k] for k in ["slope", "tree", "shrub", "gain"]], dtype=np.float64
    )
    dist = np.empty(grid.dem.shape, dtype=np.float64)
    successor = np.empty(grid.dem.shape, dtype=np.int64)
    pointers = [ctypes.c_void_p(a.ctypes.data) for a in [*arrays, valid, edges, w]]
    handle = native.hm_start(
        *grid.dem.shape,
        grid.resolution,
        grid.maximum,
        math.degrees(1.0),
        math.sqrt(2),
        *pointers,
        end[0] * grid.dem.shape[1] + end[1],
        initial,
        ctypes.c_void_p(dist.ctypes.data),
        ctypes.c_void_p(successor.ctypes.data)
    )
    if not handle:
        raise MemoryError("Approach heap exceeds processing memory guard")
    try:
        while True:
            # Return to Python regularly for alarm/cancellation handling. No
            # reordered publication and no unbounded native blocking call.
            status = native.hm_step(handle, 4096)
            if status < 0:
                raise MemoryError("Approach heap exceeds processing memory guard")
            if status == 0:
                break
    finally:
        native.hm_stop(handle)
    return Cells(dist), Cells(dist, successor)
