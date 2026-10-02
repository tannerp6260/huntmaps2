"""Explicit hunter waypoint records, stored outside immutable analysis runs."""

import uuid
from .catalog import STATE, Run, read
from .jobs import write
from .storage import transaction
from . import first_person as fp


def path(ident):
    Run(ident)
    return STATE / "manual-observers" / (ident + ".json")


def records(ident):
    return read(path(ident), {})


def fields(body):
    name = body.get("name", "Nearby observer")
    notes = body.get("notes", "")
    status = body.get("status", "needs inspection")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError("Give the waypoint a name of 1–100 characters.")
    if not isinstance(notes, str) or len(notes) > 10000:
        raise ValueError("Notes are limited to 10,000 characters.")
    if status not in ["unmarked", "keep", "reject", "needs inspection"]:
        raise ValueError("Choose a valid waypoint decision.")
    return dict(name=name.strip(), notes=notes, status=status)


def create(ident, body):
    pose = fp.observer(ident, body.get("anchor"), body)
    record = dict(
        pose,
        **fields(body),
        id="manual-" + uuid.uuid4().hex,
        kind="provisional-manual-observer",
        run_id=ident,
        analysis="No full-area analysis calculated",
        access="Legal access, footing and sightlines unverified",
        foliage_assumption="dense",
        foliage_radius_m=120
    )
    with transaction(path(ident), {}) as data:
        data[record["id"]] = record
    return record


def update(ident, key, body):
    with transaction(path(ident), {}) as data:
        if key not in data:
            raise ValueError("Unknown provisional waypoint.")
        data[key].update(fields(body))
        result = data[key]
    return result


def delete(ident, key):
    with transaction(path(ident), {}) as data:
        if key not in data:
            raise ValueError("Unknown provisional waypoint.")
        del data[key]
    return dict(deleted=key)
