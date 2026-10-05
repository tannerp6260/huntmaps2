"""Run-scoped, revision-guarded guided approach review. Historical results are immutable."""

from .config import STATE
from .storage import read_json, write, locked

VERSION = 1


def path(run):
    from .catalog import Run

    Run(run)
    return STATE / "approach-reviews" / (run + ".json")


def records(run):
    v = read_json(path(run))
    if v is not None and (
        not isinstance(v, dict)
        or v.get("version") != VERSION
        or not isinstance(v.get("queue"), list)
        or not isinstance(v.get("drafts"), dict)
        or type(v.get("revision")) is not int
        or v["revision"] < 0
        or any(not isinstance(cid, str) for cid in v["queue"])
        or len(set(v["queue"])) != len(v["queue"])
        or any(not isinstance(d, dict) for d in v["drafts"].values())
    ):
        raise ValueError("Unsupported approach review; restore a compatible backup")
    return v


def readiness(run, points):
    v = records(run)
    retained = [cid for cid, p in points.items() if p.get("shortlisted")]
    unresolved = [cid for cid in retained if not points[cid].get("approach")]
    return dict(
        active=bool(v), ready=bool(retained) and not unresolved, unresolved=unresolved
    )


def get(run, jobs=None):
    from .workflow import get as workflow

    v = records(run)
    if not v:
        return None
    return dict(v, **readiness(run, workflow(run, jobs)["points"]))


def matches(draft, scenario):
    if not draft.get("boundary_confirmed"):
        return False

    def normalized(v):
        if isinstance(v, float):
            return round(v, 8)
        if isinstance(v, list):
            return [normalized(x) for x in v]
        if isinstance(v, dict):
            return {k: normalized(x) for k, x in v.items()}
        return v

    fields = (
        "travel_area",
        "exclusions",
        "weights",
        "maximum_slope_deg",
        "start",
        "pinned",
    )
    return all(
        normalized(draft.get(k)) == normalized(scenario.get(k)) for k in fields
    ) and all(sorted(draft[k]) == sorted(scenario[k]) for k in ("network_ids", "kinds"))


def save(run, body, jobs=None):
    from .workflow import get as workflow
    from .approach_service import geometry, status

    with locked(STATE / "maintenance"), locked(path(run)):
        state = workflow(run, jobs)
        v = records(run) or dict(
            version=VERSION, revision=0, queue=[], drafts={}, active_point=None
        )
        if body.get("revision") != v["revision"]:
            raise ValueError("Approach review changed; reload before saving")
        if body.get("workflow_revision") != state["revision"]:
            raise ValueError("Shortlist changed; reload before saving review")
        ids = body.get("ids", [])
        if (
            not isinstance(ids, list)
            or len(ids) > 250
            or any(not isinstance(cid, str) for cid in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Choose distinct shortlisted setup IDs")
        retained = {cid for cid, p in state["points"].items() if p.get("shortlisted")}
        if set(ids) != retained:
            raise ValueError("Review order must include the current shortlist")
        # Existing order is stable; new/restored points append in the supplied coverage order.
        v["queue"] = [cid for cid in v["queue"] if cid in retained]
        v["queue"] += [cid for cid in ids if cid not in v["queue"]]
        cid = body.get("active_point")
        if cid is not None and cid not in retained:
            raise ValueError("Focus a current shortlisted setup")
        v["active_point"] = cid
        if body.get("draft") is not None:
            if cid is None or body.get("point") != state["points"][cid]["point"]:
                raise ValueError(
                    "Waypoint changed; reload before saving its preferences"
                )
            draft = body["draft"]
            if not isinstance(draft, dict) or not {
                "travel_area",
                "exclusions",
                "weights",
                "maximum_slope_deg",
                "network_ids",
                "kinds",
                "boundary_confirmed",
            }.issubset(draft):
                raise ValueError("Invalid approach preferences")
            if draft.get("travel_area") is not None:
                geometry(draft["travel_area"])
            if not isinstance(draft["exclusions"], list):
                raise ValueError("Choose a list of areas to avoid")
            for g in draft["exclusions"]:
                geometry(g)
            weights = draft.get("weights", {})
            if set(weights) != {"slope", "gain", "tree", "shrub"} or any(
                type(w) not in (int, float) or not 0 <= w <= 5 for w in weights.values()
            ):
                raise ValueError("Approach preferences must range from zero to five")
            slope = draft.get("maximum_slope_deg")
            if type(slope) not in (int, float) or not 0 < slope <= 60:
                raise ValueError("Choose a slope limit between zero and 60 degrees")
            if type(draft.get("boundary_confirmed")) is not bool:
                raise ValueError("Confirm the approach search boundary")
            if draft["boundary_confirmed"] and draft["travel_area"] is None:
                raise ValueError("Choose a search area before confirming its boundary")
            for field in ("network_ids", "kinds"):
                if not isinstance(draft.get(field), list) or any(
                    not isinstance(s, str) for s in draft[field]
                ):
                    raise ValueError("Invalid network sources")
            for field in ("start", "pinned"):
                if draft.get(field) is not None:
                    geometry(dict(type="Point", coordinates=draft[field]), False)
            latest = draft.get("scenario")
            if latest:
                s = status(latest, jobs)
                if s["scenario"]["run_id"] != run or cid not in [
                    p["id"] for p in s["scenario"]["points"]
                ]:
                    raise ValueError("Comparison belongs to a different setup or run")
            index = draft.get("alternative", 0)
            if type(index) is not int or index < 0:
                raise ValueError("Choose an alternative index")
            if type(draft.get("attempted", False)) is not bool:
                raise ValueError("Invalid comparison attempt state")
            selected = state["points"][cid].get("approach")
            if selected:
                from . import workflow

                saved = status(selected["scenario"], jobs)["scenario"]
                if not matches(draft, saved):
                    workflow.decide(
                        run,
                        cid,
                        dict(
                            action="unselect",
                            revision=state["revision"],
                            point=state["points"][cid]["point"],
                        ),
                        jobs,
                    )
            fields = (
                "travel_area",
                "exclusions",
                "weights",
                "maximum_slope_deg",
                "network_ids",
                "kinds",
                "boundary_confirmed",
                "scenario",
                "alternative",
                "start",
                "pinned",
                "attempted",
            )
            draft = dict(
                draft, attempted=draft.get("attempted", False), alternative=index
            )
            v["drafts"][cid] = dict(
                {k: draft.get(k) for k in fields}, point=state["points"][cid]["point"]
            )
        v["revision"] += 1
        write(path(run), v)
    return get(run, jobs)
