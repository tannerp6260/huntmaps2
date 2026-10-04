"""Versioned decisions separate from immutable analyses and legacy annotations."""

import time
from .config import STATE
from .storage import read_json, write, locked
from .approach_service import digest

VERSION = 2


def path(run):
    from .catalog import Run

    Run(run)
    return STATE / "workflows" / (run + ".json")


def records(run):
    value = read_json(path(run), dict(version=VERSION, revision=0, points={}))
    if value.get("version") not in (1, VERSION) or not isinstance(
        value.get("points"), dict
    ):
        raise ValueError(
            "Unsupported workflow record; preserve it and restore a compatible backup"
        )
    if (
        type(value.get("revision")) is not int
        or value["revision"] < 0
        or any(not isinstance(v, dict) for v in value["points"].values())
    ):
        raise ValueError(
            "Damaged workflow record; preserve it and restore a compatible backup"
        )
    return value


def point(run, cid, jobs=None, run_data=None):
    from .working_waypoints import DisplayRun

    r = run_data if run_data is not None else DisplayRun(run, jobs)
    p = r.candidate(cid)
    return dict(
        id=cid,
        longitude=p["longitude"],
        latitude=p["latitude"],
        revision=p.get("working_revision", digest([p["longitude"], p["latitude"]])),
    )


def selection(run, cid, value, jobs=None, cache=None):
    from .approach_service import status

    if not value:
        return None
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("scenario"), str)
        or type(value.get("alternative")) is not int
    ):
        raise ValueError(
            "Damaged saved approach selection; restore its workflow backup"
        )
    if cache is not None and value["scenario"] in cache:
        s = cache[value["scenario"]]
    else:
        s = status(value["scenario"], jobs)
        if cache is not None:
            cache[value["scenario"]] = s
    if (
        s["scenario"]["run_id"] != run
        or s["stale"]
        or cid in s.get("point_stale", {})
        or not s["results"]
    ):
        return None
    matches = [r for r in s["results"]["results"] if r["point"]["id"] == cid]
    if (
        not matches
        or type(value["alternative"]) is not int
        or not 0 <= value["alternative"] < len(matches[0]["alternatives"])
    ):
        return None
    if value.get("seal") != s["results"]["sha256"]:
        return None
    return value


def get(run, jobs=None):
    from .approach_service import point_snapshot
    from . import first_person as fp

    value = records(run)
    run_data, legacy = point_snapshot(run, jobs)
    result = {}
    statuses = {}
    for cid in dict.fromkeys([*legacy, *value["points"]]):
        saved = value["points"].get(cid, {})
        try:
            current = point(run, cid, jobs, run_data)
        except (KeyError, ValueError):
            continue
        same = saved.get("point") == current
        dismissed = saved.get("dismissed", False)
        shortlisted = saved.get("shortlisted", cid in legacy) and not dismissed
        selected = (
            selection(run, cid, saved.get("approach"), jobs, statuses)
            if same and shortlisted
            else None
        )
        viewed = None
        fidelity = None
        if same and saved.get("viewed"):
            try:
                scene = fp.scene(run, cid, run_data=run_data, orientation=False)
                if scene.get("key") == saved["viewed"] and all(
                    scene["observer"][k] == current[k]
                    for k in ("longitude", "latitude")
                ):
                    viewed = saved["viewed"]
                    fidelity = (
                        "lidar" if scene.get("fine_observer_available") else "terrain"
                    )
            except (ValueError, OSError):
                pass
        result[cid] = dict(
            point=current,
            shortlisted=shortlisted,
            dismissed=dismissed,
            undo_revision=saved.get("undo_revision"),
            legacy=not bool(saved),
            approach=selected,
            viewed=viewed,
            fidelity=fidelity,
            confirmed=bool(saved.get("confirmed") and selected and viewed),
            stale=bool(saved and not same),
        )
    return dict(version=VERSION, revision=value["revision"], points=result)


def decide(run, cid, body, jobs=None):
    with locked(STATE / "maintenance"), locked(path(run)):
        value = records(run)
        if body.get("revision") != value["revision"]:
            raise ValueError("Workflow changed; reload before submitting this decision")
        current = point(run, cid, jobs)
        if body.get("point") != current:
            raise ValueError("Waypoint changed; reload its exact current revision")
        old = value["points"].get(cid, {})
        if old.get("point") != current:
            from .approach_service import point_snapshot

            old = dict(
                shortlisted=old.get("shortlisted", cid in point_snapshot(run, jobs)[1]),
                dismissed=old.get("dismissed", False),
            )
        entry = dict(old, point=current)
        action = body.get("action")
        if action in ("shortlist", "remove", "dismiss", "restore"):
            entry.pop("undo", None)
            entry.pop("undo_revision", None)
            if action == "dismiss":
                entry["undo"] = {
                    k: v for k, v in old.items() if k not in ("undo", "undo_revision")
                }
                entry["undo_revision"] = value["revision"] + 1
            entry["dismissed"] = (
                old.get("dismissed", False)
                if action == "remove"
                else action == "dismiss"
            )
            entry["shortlisted"] = action == "shortlist"
            entry["confirmed"] = False
            if action in ("remove", "dismiss", "restore"):
                entry.pop("approach", None)
        elif action == "undo":
            if (
                old.get("undo_revision") != value["revision"]
                or body.get("undo_revision") != value["revision"]
            ):
                raise ValueError(
                    "Decision changed; use Restore instead of outdated Undo"
                )
            entry = dict(old["undo"], point=current)
            entry.pop("undo", None)
            entry.pop("undo_revision", None)
        elif action == "unselect":
            entry.pop("approach", None)
            entry["confirmed"] = False
        elif action == "approach":
            if (
                not isinstance(body.get("scenario"), str)
                or type(body.get("alternative")) is not int
            ):
                raise ValueError("Choose a saved scenario and an integer alternative")
            state = get(run, jobs)["points"].get(cid, {})
            if not state.get("shortlisted"):
                raise ValueError("Shortlist this setup before selecting an approach")
            from .approach_service import status

            s = status(body["scenario"], jobs)
            chosen = dict(
                scenario=body["scenario"],
                alternative=body["alternative"],
                seal=s["results"]["sha256"] if s["results"] else None,
            )
            if not selection(run, cid, chosen, jobs):
                raise ValueError("Choose a completed, current approach alternative")
            if old.get("approach") != chosen:
                entry["confirmed"] = False
            entry.update(shortlisted=True, approach=chosen)
        elif action == "viewed":
            from .first_person import scene

            meta = scene(run, cid)
            if (
                meta.get("status") != "ready"
                or meta.get("key") != body.get("scene")
                or any(
                    meta["observer"][k] != current[k] for k in ("longitude", "latitude")
                )
            ):
                raise ValueError(
                    "Open the current scene successfully before recording viewing"
                )
            if old.get("viewed") != meta["key"]:
                entry["confirmed"] = False
            entry["viewed"] = meta["key"]
        elif action == "confirm":
            state = get(run, jobs)["points"].get(cid, {})
            if (
                not state.get("shortlisted")
                or not state.get("approach")
                or not state.get("viewed")
            ):
                raise ValueError(
                    "Confirmation requires a shortlisted setup, current selected approach and successfully opened current scene"
                )
            entry["confirmed"] = True
        else:
            raise ValueError(
                "Choose shortlist, dismiss, restore, undo, remove, unselect, approach, viewed or confirm"
            )
        entry["updated"] = time.time()
        value["points"][cid] = entry
        value["version"] = VERSION
        value["revision"] += 1
        write(path(run), value)
    return get(run, jobs)


def invalidate_confirmation(run, cid):
    with locked(path(run)):
        value = records(run)
        entry = value["points"].get(cid)
        if entry and entry.get("confirmed"):
            entry["confirmed"] = False
            value["revision"] += 1
            write(path(run), value)
