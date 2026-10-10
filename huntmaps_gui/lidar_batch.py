"""Decode shared lidar once into bounded, disposable observer spools.

Source/chunk/return ordering and coordinate arithmetic match _crop_points. No
thinning, radius changes, persistent point cache or simultaneous scene meshes.
"""

from contextlib import ExitStack, contextmanager
import tempfile
import numpy as np
from glassing.acquire import digest
from .sampling import stamp

MAX_SPOOL_BYTES = 384 * 1024**2


class CapacityExceeded(Exception):
    pass


class SourceChanged(ValueError):
    pass


class Crops:
    def __init__(self, run, ids, sources, stack):
        from .first_person_worker import deps
        from . import first_person as fp
        from .downloads import check_space

        laspy, pyproj = deps()
        self.files = {cid: stack.enter_context(tempfile.TemporaryFile()) for cid in ids}
        self.counts = {cid: 0 for cid in ids}
        self.hist = {cid: {} for cid in ids}
        self.refs = {cid: set() for cid in ids}
        self.sources = {path: (stamp(path), h) for s, path, h in sources}
        total_bytes = 0
        self.verify(full=True)
        for s, path, h in sources:
            relevant = [cid for cid in ids if cid in s["candidates"]]
            if not relevant:
                continue
            fp.stage("Reading shared measured lidar returns · " + path.name)
            with laspy.open(path, laz_backend=laspy.LazBackend.Lazrs) as reader:
                crs = reader.header.parse_crs()
                if crs is None:
                    raise ValueError("Lidar CRS missing")
                vertical = [a for a in crs.axis_info if a.direction.lower() == "up"]
                if len(vertical) != 1:
                    raise ValueError(
                        "Explicit lidar vertical reference and units required"
                    )
                unit = vertical[0].unit_conversion_factor
                vref = crs.sub_crs_list[-1].to_wkt() if crs.is_compound else None
                if not vref:
                    raise ValueError("Lidar vertical datum missing")
                for cid in relevant:
                    self.refs[cid].add(vref)
                    if len(self.refs[cid]) > 1:
                        raise ValueError(
                            "Incompatible lidar vertical references; no guessed elevation adjustment"
                        )
                tr = pyproj.Transformer.from_crs(
                    crs, run.config["epsg"], always_xy=True
                )
                for chunk in reader.chunk_iterator(100000):
                    x, y = tr.transform(np.asarray(chunk.x), np.asarray(chunk.y))
                    z = np.asarray(chunk.z) * unit
                    classes = np.asarray(chunk.classification)
                    valid = (
                        ~np.asarray(chunk.withheld, dtype=bool)
                        & ~np.isin(classes, [7, 18])
                        & np.isfinite(z)
                    )
                    for cid in relevant:
                        p = run.points[cid]
                        keep = (np.hypot(x - p["x"], y - p["y"]) <= 308) & valid
                        a = np.column_stack(
                            [x[keep] - p["x"], y[keep] - p["y"], z[keep], classes[keep]]
                        ).astype(np.float64)
                        self.counts[cid] += len(a)
                        if self.counts[cid] > 8_000_000:
                            # Fall back to the original per-observer guard; one
                            # overfull observer must not block valid neighbors.
                            raise CapacityExceeded()
                        total_bytes += a.nbytes
                        if total_bytes > MAX_SPOOL_BYTES:
                            raise CapacityExceeded()
                        check_space(fp.HOME, a.nbytes)
                        a.tofile(self.files[cid])
                        u, n = np.unique(classes[keep], return_counts=True)
                        for k, v in zip(u, n):
                            key = str(k)
                            self.hist[cid][key] = self.hist[cid].get(key, 0) + int(v)
        self.verify()

    def verify(self, full=False):
        for path, (identity, h) in self.sources.items():
            if stamp(path) != identity or (full and digest(path) != h):
                raise SourceChanged(
                    "Lidar source changed during preparation: " + str(path)
                )

    def get(self, cid, radius=308):
        self.verify()
        spool = self.files[cid]
        spool.seek(0)
        points = np.fromfile(
            spool, dtype=np.float64, count=self.counts[cid] * 4
        ).reshape(-1, 4)
        hist = self.hist[cid]
        if radius < 308:
            points = points[np.hypot(points[:, 0], points[:, 1]) <= radius]
            u, n = np.unique(points[:, 3].astype(np.uint8), return_counts=True)
            hist = {str(k): int(v) for k, v in zip(u, n)}
        elif radius != 308:
            raise ValueError("Batch crop only supports radii up to 308 m")
        return points, next(iter(self.refs[cid]), ""), hist


@contextmanager
def crop_batch(run, ids, sources):
    """Use one sequential decoder; excess spool capacity uses the original path."""
    with ExitStack() as stack:
        crops = None
        if sources and len(ids) > 1:
            try:
                crops = Crops(run, ids, sources, stack)
            except SourceChanged:
                raise
            except (CapacityExceeded, ValueError, MemoryError):
                stack.close()
                from . import first_person as fp

                fp.stage(
                    "Shared crop unavailable within guards; preparing observers sequentially"
                )
        yield crops
        if crops is not None:
            crops.verify(full=True)
