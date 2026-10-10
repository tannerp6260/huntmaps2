"""GUI source validation and retained evidence; frozen acquisition stays unchanged."""

from contextlib import contextmanager
from contextvars import ContextVar
import datetime
import json
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

from glassing.acquire import digest
from .storage import write

_context = ContextVar("acquisition_validation", default=None)


class ProviderResponseError(ValueError):
    """A received response cannot be used as the requested analytical source."""


@contextmanager
def validating(config, inputs):
    token = _context.set((config, inputs))
    try:
        yield
    finally:
        _context.reset(token)


def label(name, metadata):
    key = Path(name).stem.split("_")[0]
    product = {
        "tree": "tree-cover",
        "shrub": "shrub-cover",
        "herb": "herb-cover",
        "dem": "DEM",
        "summer": "summer-range",
        "winter": "winter-range",
    }.get(key, Path(name).name)
    return f"{metadata.get('provider', 'Source provider')} {product} service"


def document_error(path):
    """Bounded extraction of OGC/HTML error text, even with image/tiff headers."""
    with Path(path).open("rb") as stream:
        head = stream.read(65536).lstrip()
    if not head.startswith(b"<"):
        return None
    try:
        value = ET.fromstring(head)
        details = [
            " ".join((node.text or "").split())
            for node in value.iter()
            if node.tag.split("}")[-1] in ("ExceptionText", "ServiceException", "title")
        ]
        return (
            "; ".join(filter(None, details))[:1000]
            or "XML/HTML response instead of source data"
        )
    except ET.ParseError:
        return "XML/HTML response instead of source data"


def validate(path, name, metadata, *, scratch_dir=None):
    path = Path(path)
    title = label(name, metadata)
    error = document_error(path)
    if error:
        raise ProviderResponseError(f"{title} returned an error: {error}")
    suffix = Path(name).suffix.lower()
    if suffix in (".tif", ".tiff"):
        from osgeo import gdal

        gdal.PushErrorHandler("CPLQuietErrorHandler")
        try:
            try:
                ds = gdal.OpenEx(str(path), gdal.OF_RASTER, allowed_drivers=["GTiff"])
                valid = (
                    ds is not None
                    and ds.RasterCount == 1
                    and ds.RasterXSize > 0
                    and ds.RasterYSize > 0
                )
                if valid:
                    band = ds.GetRasterBand(1)
                    pixel_bytes = max(1, gdal.GetDataTypeSize(band.DataType) // 8)
                    columns = min(ds.RasterXSize, (8 * 1024**2) // pixel_bytes)
                    rows = max(1, min(256, (8 * 1024**2) // (columns * pixel_bytes)))
                    for y in range(0, ds.RasterYSize, rows):
                        for x in range(0, ds.RasterXSize, columns):
                            gdal.ErrorReset()
                            block = band.ReadRaster(
                                x,
                                y,
                                min(columns, ds.RasterXSize - x),
                                min(rows, ds.RasterYSize - y),
                            )
                            if (
                                block is None
                                or gdal.GetLastErrorType() >= gdal.CE_Failure
                            ):
                                valid = False
                                break
                        if not valid:
                            break
                ds = None
            except RuntimeError:
                valid = False
        finally:
            gdal.PopErrorHandler()
        if not valid:
            raise ProviderResponseError(
                f"{title} returned an unreadable or invalid GeoTIFF"
            )
        context = _context.get()
        if context:
            from glassing.owner_data import coverage, grid_bounds

            config, inputs = context
            key = Path(name).stem.split("_")[0]
            try:
                diagnostic = coverage(
                    path,
                    grid_bounds(config, inputs),
                    config["epsg"],
                    config["resolution_m"],
                    vegetation=key != "dem",
                )
            except (ValueError, RuntimeError, TypeError, AttributeError) as error:
                raise ProviderResponseError(
                    f"{title} returned an unusable raster: {error}"
                ) from error
            if not diagnostic["geographic_coverage"] or (
                key == "dem" and diagnostic["unknown_cells"]
            ):
                raise ProviderResponseError(
                    f"{title} returned insufficient raster coverage"
                )
    elif suffix in (".json", ".geojson"):
        try:
            value = json.loads(path.read_text())
        except (ValueError, UnicodeError) as error:
            raise ProviderResponseError(f"{title} returned invalid JSON") from error
        if not isinstance(value, dict) or value.get("error"):
            detail = (
                value.get("error") if isinstance(value, dict) else "expected an object"
            )
            raise ProviderResponseError(
                f"{title} returned an error: {str(detail)[:1000]}"
            )
        if suffix == ".geojson" and (
            value.get("type") != "FeatureCollection"
            or not isinstance(value.get("features"), list)
            or value.get("exceededTransferLimit")
        ):
            raise ProviderResponseError(
                f"{title} returned an incomplete or invalid GeoJSON response"
            )
        if suffix == ".geojson" and _context.get():
            import tempfile
            from glassing.owner_data import normalize_range

            scratch = Path(scratch_dir) if scratch_dir is not None else path.parent
            scratch.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="range-validation-", dir=scratch
            ) as folder:
                try:
                    normalize_range(
                        dict(path=str(path), sha256=digest(path)),
                        Path(folder),
                        Path(name).stem,
                    )
                except (ValueError, KeyError, TypeError) as error:
                    raise ProviderResponseError(
                        f"{title} returned invalid range data: {error}"
                    ) from error


def retain_rejected(root, path, name, entry, reason):
    """Record provenance before moving bytes; no rejected entry is a cache hit."""
    root, path = Path(root), Path(path)
    folder = root / "rejected" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    write(
        folder / "metadata.json",
        dict(
            name=name,
            original_path=str(path),
            source=entry,
            sha256=digest(path),
            bytes=path.stat().st_size,
            reason=str(reason),
            rejected_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ),
    )
    path.replace(folder / ("response" + Path(name).suffix))
    return folder
