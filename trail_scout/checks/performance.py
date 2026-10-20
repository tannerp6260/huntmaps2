"""Real bounded corridor measurements; OS cache is deliberately not flushed."""

from datetime import date
import json
from pathlib import Path
import resource
import tempfile
import time
import uuid

from trail_scout.storage import Paths, atomic, seal
from trail_scout.sources import Pack
from trail_scout.network import starts
from trail_scout.planner import calculate


def main():
    out = Path(tempfile.mkdtemp(prefix="trailscout-performance-"))
    paths = Paths(state=out / "state")
    begin = time.perf_counter()
    pack = Pack(paths)
    source_validation = time.perf_counter() - begin
    entries = starts(pack, date(2026, 10, 31))
    rows = []

    def run(label, body):
        ident = uuid.uuid4().hex
        folder = paths.artifact("analyses", ident)
        phases = []

        def progress(stage, n, total, message):
            if not phases or phases[-1]["stage"] != stage:
                phases.append(
                    dict(stage=stage, seconds=time.perf_counter() - begin_run)
                )

        begin_run = time.perf_counter()
        result = calculate(paths, pack, body, folder, progress)
        seal(folder / "result.json")
        elapsed = time.perf_counter() - begin_run
        row = dict(
            label=label,
            seconds=elapsed,
            analysis_id=ident,
            grid=result["grid"],
            search=result["search"],
            recommended=result["recommended"],
            option_count=len(result["options"]),
            phases=phases,
            process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / 1024,
        )
        rows.append(row)
        atomic(
            out / "measurements.json",
            dict(
                source_validation_seconds=source_validation,
                rows=rows,
                note="Fresh derived cache means cold; operating-system page cache retained. Timings include actual terrain windows, network/spur/candidate analysis, masks, coverage, schedules, local relief and JSON publication. No browser rendering or source downloading. RSS is cumulative process peak.",
            ),
        )
        print(
            label,
            f"{elapsed:.3f}s",
            result["search"],
            "options",
            len(result["options"]),
            flush=True,
        )
        return result

    soap = next(e for e in entries if e["label"] == "Soap Creek · entry")
    mill = next(e for e in entries if e["label"] == "Flattop Bench · entry")
    body = dict(start_id=soap["id"], candidate_budget=32)
    first = run("soap cold", body)
    run("soap warm", body)
    run("soap schedule-only edit", dict(body, schedule=dict(am_end_offset=150)))
    run(
        "soap profile-only edit",
        dict(body, profile=dict(preset="together", pace_mph=1.4)),
    )
    second = run("flattop bench cold", dict(body, start_id=mill["id"]))
    run("flattop bench warm", dict(body, start_id=mill["id"]))
    atomic(
        out / "summary.json",
        dict(
            evidence=str(out),
            source_validation_seconds=source_validation,
            measurements=rows,
            demonstrations=[
                {
                    k: r[k]
                    for k in (
                        "analysis_id",
                        "start",
                        "grid",
                        "search",
                        "recommended",
                        "options",
                    )
                }
                for r in (first, second)
            ],
        ),
    )
    print("PERFORMANCE EVIDENCE:", out, flush=True)


if __name__ == "__main__":
    main()
