"""Publication boundary for derived generations; incomplete evidence is retained."""

from pathlib import Path
import uuid

from trail_scout.storage import atomic, read, IntegrityError


def ready(folder):
    marker = Path(folder) / "ready.json"
    if not marker.exists():
        return False
    try:
        record = read(marker)
    except (ValueError, OSError) as error:
        raise IntegrityError(
            "Invalid derived publication marker; retained for diagnosis"
        ) from error
    if (
        not isinstance(record, dict)
        or type(record.get("version")) is not int
        or record != dict(version=1, key=Path(folder).name)
    ):
        raise IntegrityError("Derived generation publication identity differs")
    return True


def begin(folder):
    folder = Path(folder)
    if folder.exists():
        if ready(folder):
            raise IntegrityError("Published derived cache cannot be overwritten")
        # Retain interrupted bytes in the same bounded application cache root.
        folder.rename(
            folder.with_name(folder.name + ".interrupted-" + uuid.uuid4().hex)
        )
    folder.mkdir(parents=True)


def publish(folder):
    marker = Path(folder) / "ready.json"
    atomic(marker, dict(version=1, key=Path(folder).name))
