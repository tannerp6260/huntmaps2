import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { api, RecordValue, defaults, miles, feet, acres, clock } from "./api";
import { ScoutMap } from "./map";
import { Recommendation } from "./recommendation";
import {
  PracticalSettings,
  PracticalResult,
  PracticalPlanSettings,
  TimedResult,
} from "./practical";
import { readWorkspace, writeWorkspace } from "./workspace";
import "./style.css";

function NumberField({
  label,
  value,
  onChange,
  step = 1,
  min = 0,
  max = 10000,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  step?: number;
  min?: number;
  max?: number;
}) {
  return (
    <label>
      {label}
      <input
        type="number"
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
function App() {
  const restored = useRef(readWorkspace());
  const [ready, setReady] = useState(false),
    [sourcesLoading, setSourcesLoading] = useState(true),
    [contextReady, setContextReady] = useState(false),
    [contextFailed, setContextFailed] = useState(false),
    [contextRetry, setContextRetry] = useState(0);
  const stateIdentity = useRef("");
  const draftQueue = useRef<Promise<unknown>>(Promise.resolve());
  const queueDraft = (settings: RecordValue) => {
    const next = draftQueue.current
      .catch(() => {})
      .then(() => api("/draft", { settings }, "PUT"));
    draftQueue.current = next;
    return next;
  };
  const [config, setConfig] = useState<RecordValue>(defaults),
    [presets, setPresets] = useState<RecordValue>({}),
    [area, setArea] = useState<RecordValue | null>(null),
    [context, setContext] = useState<RecordValue | null>(null),
    [entries, setEntries] = useState<RecordValue[]>([]);
  const [result, setResult] = useState<RecordValue | null>(null),
    [selected, setSelected] = useState(""),
    [mode, setMode] = useState(restored.current?.mode || "am"),
    [job, setJob] = useState<RecordValue | null>(null),
    [history, setHistory] = useState<RecordValue[]>([]),
    [saved, setSaved] = useState<RecordValue[]>([]),
    [savedPlan, setSavedPlan] = useState<RecordValue | null>(null);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [name, setName] = useState(restored.current?.name || "TrailScout outing"),
    [editMode, setEditMode] = useState(""),
    [segment, setSegment] = useState<RecordValue | null>(null),
    [point, setPoint] = useState<RecordValue | null>(null),
    [profilePoint, setProfilePoint] = useState<RecordValue | null>(null),
    [tab, setTab] = useState(restored.current?.tab || "route"),
    [importText, setImportText] = useState(""),
    [manualNote, setManualNote] = useState(""),
    [sourceKind, setSourceKind] = useState("closed_roads"),
    [sourceDate, setSourceDate] = useState("2026-10-19"),
    [compareSaved, setCompareSaved] = useState<RecordValue[]>([]);
  const editRevision = useRef(0),
    openRevision = useRef(0);
  const inspectionRef = useRef<HTMLElement>(null),
    scheduleRef = useRef<HTMLElement>(null),
    saveRef = useRef<HTMLDivElement>(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const jobRef = useRef(""),
    configRef = useRef(config),
    dirtyRef = useRef(false),
    editCorner = useRef<number[] | null>(null),
    mounted = useRef(true);
  configRef.current = config;
  dirtyRef.current = dirty;
  const option =
    result?.options.find((o: RecordValue) => o.id === selected) || null;
  const currentSchedule = option?.schedules[mode];
  const previewStale =
    dirty ||
    (!!result && JSON.stringify(config) !== JSON.stringify(result.settings));
  const selectOption = (id: string) => {
    openRevision.current++;
    setSelected(id);
    setProfilePoint(null);
    setPoint(null);
    setSegment(null);
  };
  const selectMode = (value: string) => {
    openRevision.current++;
    setMode(value);
    if (result?.recommended[value]) selectOption(result.recommended[value]);
  };
  const inspect = (value: string) => {
    setTab(value);
    requestAnimationFrame(() => {
      const target =
        value === "schedule" ? scheduleRef.current : inspectionRef.current;
      target?.focus({ preventScroll: true });
      target?.scrollIntoView({ block: "start" });
    });
  };
  const change = (patch: RecordValue) => {
    editRevision.current++;
    openRevision.current++;
    setConfig((c) => ({ ...c, ...patch }));
    setDirty(true);
    setNotice(
      "Inputs changed. Recalculate to update routes and schedules. The previous result is retained.",
    );
  };
  const profileChange = (k: string, n: number) =>
    change({ profile: { ...config.profile, [k]: n } });
  const scheduleChange = (k: string, n: any) =>
    change({ schedule: { ...config.schedule, [k]: n } });
  const protectError = (fn: () => Promise<void>) => {
    setError("");
    fn().catch((e) => setError(String(e.message || e)));
  };
  const refreshSaves = async () => setSaved(await api("/plans"));
  useEffect(() => {
    mounted.current = true;
    const initialEditRevision = editRevision.current;
    const initialOpenRevision = openRevision.current;
    (async () => {
      const [areas, p, d, h, plans, current] = await Promise.all([
        api("/areas").catch((e) => {
          setError(
            "Source package unavailable: " +
              e.message +
              ". Saved versions remain available below.",
          );
          return [];
        }),
        api("/profiles"),
        api("/draft"),
        api("/jobs"),
        api("/plans"),
        api("/health"),
      ]);
      if (!mounted.current) return;
      stateIdentity.current = current.state;
      if (restored.current?.state !== current.state) {
        restored.current = null;
        setMode("am");
        setName("TrailScout outing");
      }
      setArea(areas[0] || null);
      setSourcesLoading(false);
      setPresets(p);
      setHistory(h);
      setSaved(plans);
      if (editRevision.current === initialEditRevision) {
        if (restored.current?.pendingSettings || d.settings)
          setConfig(restored.current?.pendingSettings || d.settings);
        else
          setConfig({
            ...defaults,
            profile: { preset: "together", ...p.together },
          });
      }
      const active = h.find((j: RecordValue) =>
        ["running", "pending", "cancelling"].includes(j.status),
      );
      if (active) {
        jobRef.current = active.id;
        setJob(active);
      } else {
        const completed = h.find(
          (j: RecordValue) => j.status === "completed" && j.kind !== "prepare",
        );
        if (completed) {
          const remembered = restored.current;
          // Restore only an analysis still present in this state's job history.
          const noNewCompletion =
            remembered?.latestCompleted === completed.analysis_id ||
            remembered?.analysisId === completed.analysis_id;
          const analysisId =
            noNewCompletion &&
            h.some(
              (j: RecordValue) =>
                j.status === "completed" &&
                j.analysis_id === remembered?.analysisId,
            )
              ? remembered!.analysisId
              : completed.analysis_id;
          const r = await api("/analyses/" + analysisId);
          if (!mounted.current || openRevision.current !== initialOpenRevision)
            return;
          const period =
            r.practical_plan &&
            ["combined", "stay"].includes(remembered?.mode || "")
              ? "am"
              : remembered?.mode || "am";
          setResult(r);
          setMode(period);
          setName(
            remembered?.name || r.start.label.split(" ·")[0] + " scouting",
          );
          setSelected(
            remembered?.analysisId === r.analysis_id &&
              r.options.some((o: RecordValue) => o.id === remembered?.selected)
              ? remembered?.selected
              : r.recommended[period] || "",
          );
          if (
            remembered?.savedId &&
            plans.some((v: RecordValue) => v.id === remembered.savedId)
          ) {
            const v = await api("/plans/" + remembered.savedId);
            if (mounted.current && openRevision.current === initialOpenRevision)
              setSavedPlan(v);
          }
          if (editRevision.current === initialEditRevision)
            setConfig(remembered?.pendingSettings || d.settings || r.settings);
          setDirty(
            editRevision.current !== initialEditRevision ||
              JSON.stringify(
                restored.current?.pendingSettings || d.settings || r.settings,
              ) !== JSON.stringify(r.settings) ||
              r.implementation !== current.implementation ||
              r.source_revision !== areas[0]?.revision ||
              (!!r.practical &&
                r.practical.package !== areas[0]?.practical?.id) ||
              (!!r.practical_plan &&
                r.practical_plan.package !== areas[0]?.practical?.id),
          );
        }
      }
    })()
      .catch((e) => setError("Workspace could not load: " + e.message))
      .finally(() => {
        if (mounted.current) {
          setReady(true);
          setSourcesLoading(false);
        }
      });
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    let live = true;
    setContextReady(false);
    setContextFailed(false);
    setContext(null);
    const widthQuery = config.vehicle_width_inches
      ? "&width=" + config.vehicle_width_inches
      : "";
    const contextRequest = api(
      "/context?date=" +
        config.date +
        "&vehicle=" +
        config.vehicle +
        widthQuery,
    )
      .then((c) => {
        if (live) setContext(c);
      })
      .catch((e) => {
        if (live) setError("Local context unavailable: " + e.message);
        return false;
      });
    const startsRequest = (
      config.restrictions.length
        ? api("/starts", {
            date: config.date,
            vehicle: config.vehicle,
            restrictions: config.restrictions,
            vehicle_width_inches: config.vehicle_width_inches ?? null,
          })
        : api(
            "/starts?date=" +
              config.date +
              "&vehicle=" +
              config.vehicle +
              widthQuery,
          )
    )
      .then((s) => {
        if (live) {
          setEntries(s);
          if (!configRef.current.start_id && s[0])
            setConfig((c) => ({ ...c, start_id: s[0].id }));
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
        return false;
      });
    Promise.all([contextRequest, startsRequest]).then(([c, s]) => {
      if (live) {
        setContextReady(c !== false && s !== false);
        setContextFailed(c === false || s === false);
      }
    });
    return () => {
      live = false;
    };
  }, [
    contextRetry,
    config.date,
    config.vehicle,
    config.vehicle_width_inches,
    JSON.stringify(config.restrictions),
  ]);
  useEffect(() => {
    if (!ready) return;
    // Keep an immediate local recovery copy until the serialized server write lands.
    writeWorkspace({ pendingSettings: config });
    const timer = setTimeout(() => {
      queueDraft(config)
        .then(() => {
          if (JSON.stringify(configRef.current) === JSON.stringify(config))
            writeWorkspace({ pendingSettings: null });
        })
        .catch((e) => setError("Draft not saved: " + e.message));
    }, 600);
    return () => clearTimeout(timer);
  }, [config, ready]);
  useEffect(() => {
    if (ready)
      writeWorkspace({
        state: stateIdentity.current,
        analysisId: result?.analysis_id || "",
        selected,
        mode,
        tab,
        name,
        savedId: savedPlan?.id || "",
        latestCompleted:
          history.find(
            (j: RecordValue) =>
              j.status === "completed" && j.kind !== "prepare",
          )?.analysis_id || "",
      });
  }, [
    ready,
    result?.analysis_id,
    selected,
    mode,
    tab,
    name,
    savedPlan?.id,
    history,
  ]);
  useEffect(() => {
    if (!job || !["pending", "running", "cancelling"].includes(job.status))
      return;
    let live = true;
    let polling = false;
    const timer = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        const j = await api("/jobs/" + job.id);
        if (!live || jobRef.current !== job.id) return;
        if (j.status === "completed") {
          if (j.kind === "prepare") {
            setArea((await api("/areas"))[0]);
            setEntries(
              await api(
                "/starts?date=" +
                  configRef.current.date +
                  "&vehicle=" +
                  configRef.current.vehicle,
              ),
            );
            setDirty(true);
            setNotice("New source snapshot prepared. Recalculate to use it.");
          } else {
            const r = await api("/analyses/" + j.analysis_id);
            if (!mounted.current || jobRef.current !== job.id) return;
            setResult(r);
            const period =
              r.practical_plan && ["combined", "stay"].includes(modeRef.current)
                ? "am"
                : modeRef.current;
            setMode(period);
            setSelected(r.recommended[period] || "");
            setPoint(null);
            setSegment(null);
            if (!dirtyRef.current)
              setNotice(
                "Comparison ready. Review a preview, then save the plan you choose.",
              );
          }
          if (!live || jobRef.current !== job.id) return;
          setJob(j);
          setHistory(await api("/jobs"));
        } else if (["failed", "cancelled", "interrupted"].includes(j.status)) {
          setJob(j);
          setError(j.error || j.status);
          setHistory(await api("/jobs"));
        } else setJob(j);
      } catch (e: any) {
        if (live)
          setError(
            "Status unavailable; work may still be running. " + e.message,
          );
      } finally {
        polling = false;
      }
    }, 600);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [job?.id, job?.status]);
  async function run() {
    if (busy || active || !ready || !contextReady || !area) return;
    openRevision.current++;
    setBusy(true);
    setError("");
    setNotice("");
    const submitted = configRef.current,
      revision = editRevision.current;
    try {
      await queueDraft(submitted);
      const j = await api("/jobs", submitted);
      jobRef.current = j.id;
      setJob(j);
      if (editRevision.current === revision) {
        setConfig(j.settings);
        setDirty(false);
      } else {
        setDirty(true);
        setNotice(
          "Calculation uses the submitted inputs; your newer edits are preserved. Recalculate when ready.",
        );
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function openSaved(id: string) {
    const revision = ++openRevision.current;
    const edit = editRevision.current;
    const v = await api("/plans/" + id);
    const r = await api("/analyses/" + v.analysis_id);
    const current = await api("/health");
    if (
      openRevision.current !== revision ||
      editRevision.current !== edit ||
      active
    )
      return;
    setProfilePoint(null);
    setPoint(null);
    setSegment(null);
    setSavedPlan(v);
    setName(v.name);
    setMode(v.mode);
    setConfig(v.settings);
    setResult(r);
    setSelected(v.option.id);
    const stale =
      v.implementation !== current.implementation ||
      v.source_revision !== area?.revision ||
      (!!v.practical && v.practical.package !== area?.practical?.id) ||
      (!!v.practical_plan && v.practical_plan.package !== area?.practical?.id);
    setDirty(stale);
    setNotice(
      stale
        ? "Saved version uses earlier source/model revisions. It remains readable/exportable; recalculate before saving an adjusted version."
        : "Opened immutable saved version " +
            v.id.slice(0, 8) +
            ". Adjusting and saving creates a new version.",
    );
  }
  async function openPreview(id: string) {
    const revision = ++openRevision.current;
    const r = await api("/analyses/" + id);
    const current = await api("/health");
    if (openRevision.current !== revision || active) return;
    setResult(r);
    setConfig(r.settings);
    const period =
      r.practical_plan && ["combined", "stay"].includes(modeRef.current)
        ? "am"
        : modeRef.current;
    setMode(period);
    setSelected(r.recommended[period] || "");
    setPoint(null);
    setSegment(null);
    setProfilePoint(null);
    setSavedPlan(null);
    const stale =
      r.implementation !== current.implementation ||
      r.source_revision !== area?.revision ||
      (!!r.practical && r.practical.package !== area?.practical?.id) ||
      (!!r.practical_plan && r.practical_plan.package !== area?.practical?.id);
    setDirty(stale);
    setNotice(
      stale
        ? "Historical preview uses earlier sources/model. Recalculate before saving."
        : "Opened calculation preview. Saving creates a separate immutable plan.",
    );
  }
  async function save() {
    if (
      !option ||
      !result ||
      previewStale ||
      active ||
      busy ||
      !currentSchedule?.feasible
    )
      return;
    setBusy(true);
    try {
      const v = await api("/plans", {
        analysis_id: result.analysis_id,
        option_id: option.id,
        mode,
        name,
        settings: config,
        parent_id: savedPlan?.id || null,
      });
      setSavedPlan(v);
      await refreshSaves();
      setNotice(
        "Saved version " +
          v.id.slice(0, 8) +
          ". Exact routes, coordinates, assumptions and schedule retained.",
      );
    } finally {
      setBusy(false);
    }
  }
  const pin = (p: RecordValue) => {
    if (
      config.pinned.some(
        (v: RecordValue) =>
          Math.abs(v.longitude - p.longitude) < 1e-8 &&
          Math.abs(v.latitude - p.latitude) < 1e-8,
      )
    )
      return;
    change({
      pinned: [
        ...config.pinned,
        { longitude: p.longitude, latitude: p.latitude },
      ],
    });
  };
  const mapPoint = (lon: number, lat: number) => {
    if (editMode === "pin") {
      pin({ longitude: lon, latitude: lat });
      setEditMode("");
    } else if (editMode === "exclude") {
      if (!editCorner.current) {
        editCorner.current = [lon, lat];
        setNotice("Choose the opposite corner of the exclusion.");
      } else {
        const [x, y] = editCorner.current;
        change({
          excluded_areas: [
            ...config.excluded_areas,
            {
              type: "Polygon",
              coordinates: [
                [
                  [x, y],
                  [lon, y],
                  [lon, lat],
                  [x, lat],
                  [x, y],
                ],
              ],
            },
          ],
        });
        editCorner.current = null;
        setEditMode("");
      }
    }
  };
  function profileHover(e: React.MouseEvent<SVGSVGElement>) {
    if (!option) return;
    const bounds = e.currentTarget.getBoundingClientRect();
    let wanted =
      Math.max(0, Math.min(1, (e.clientX - bounds.left) / bounds.width)) *
      option.movement.distance_m;
    for (const leg of option.legs) {
      if (wanted <= leg.distance_m) {
        const nearest = leg.profile.reduce((a: RecordValue, b: RecordValue) =>
          Math.abs(a.distance_m - wanted) < Math.abs(b.distance_m - wanted)
            ? a
            : b,
        );
        setProfilePoint(nearest);
        return;
      }
      wanted -= leg.distance_m;
    }
  }

  function profilePath() {
    if (!option) return "";
    const pts = option.legs.flatMap((l: RecordValue) => l.profile);
    const min = Math.min(...pts.map((p: RecordValue) => p.elevation_m)),
      max = Math.max(...pts.map((p: RecordValue) => p.elevation_m));
    let offset = 0;
    const chart: any[] = [];
    for (const leg of option.legs) {
      for (const p of leg.profile)
        chart.push([offset + p.distance_m, p.elevation_m]);
      offset += leg.distance_m;
    }
    return chart
      .map(
        ([x, y], i) =>
          (i ? "L" : "M") +
          ((x / offset) * 800).toFixed(2) +
          "," +
          (110 - ((y - min) / Math.max(20, max - min)) * 85).toFixed(2),
      )
      .join(" ");
  }
  const active =
    !!job && ["pending", "running", "cancelling"].includes(job.status);
  return (
    <>
      <header>
        <a className="brand" href="/" aria-label="TrailScout home">
          <svg width="34" height="34" viewBox="0 0 34 34">
            <circle cx="17" cy="17" r="15" fill="none" stroke="currentColor" />
            <path d="M9 23 17 7 25 23 17 19Z" fill="currentColor" />
            <path d="m12 25 5-6 5 6" stroke="currentColor" fill="none" />
          </svg>
          <span>
            TrailScout<small>TRAIL & GLASSING PLANNER</small>
          </span>
        </a>
        <div className="header-status">
          <span className="dot" />{" "}
          {sourcesLoading
            ? "Checking local sources…"
            : area
              ? "Local sources ready"
              : "Sources need attention"}
          <span className="tag">PROVISIONAL DESKTOP PLANS</span>
        </div>
      </header>
      <div className="workspace">
        <aside className="controls">
          <div className="eyebrow">PLAN AN OUTING</div>
          <h1>Choose a manageable walk.</h1>
          <fieldset className="input-fields" disabled={!ready}>
            <div className="source-status">
              {area ? (
                <>
                  <span className="dot" /> Colorado GMU 54 · Core ready ·{" "}
                  {area.version}
                </>
              ) : (
                <>
                  {sourcesLoading
                    ? "Checking real local sources…"
                    : "Core package needs attention."}
                </>
              )}
            </div>
            <label>
              Who is going?
              <select
                value={config.profile.preset}
                onChange={(e) =>
                  change({
                    profile: {
                      preset: e.target.value,
                      ...presets[e.target.value],
                    },
                  })
                }
              >
                <option value="together">Together · conservative</option>
                <option value="dad">Dad · easy pace</option>
                <option value="tanner">Tanner · moderate</option>
                <option value="extended">
                  Extended family · 3 mi / 900 ft
                </option>
              </select>
            </label>

            <div className="field-row">
              <NumberField
                label="Daily miles limit"
                value={config.profile.max_miles ?? 2.5}
                onChange={(n) => profileChange("max_miles", n)}
                step={0.25}
              />
              <NumberField
                label="Gain limit · ft"
                value={config.profile.max_gain_ft ?? 750}
                onChange={(n) => profileChange("max_gain_ft", n)}
                step={50}
              />
            </div>
            <div className="reserve" aria-label="Usable effort budget">
              <strong>
                Usable after reserve:{" "}
                {Number(
                  (
                    (config.profile.max_miles ?? 2.5) *
                    (1 - (config.profile.reserve_fraction ?? 0.25))
                  ).toFixed(3),
                )}{" "}
                mi /{" "}
                {Number(
                  (
                    (config.profile.max_gain_ft ?? 750) *
                    (1 - (config.profile.reserve_fraction ?? 0.25))
                  ).toFixed(1),
                )}{" "}
                ft
              </strong>
              <span>
                {Math.round((config.profile.reserve_fraction ?? 0.25) * 100)}%
                held from nominal daily limits above. Includes the complete
                return; limits never relax automatically.
              </span>
            </div>
            <div className="field-row">
              <label>
                Outing date
                <input
                  type="date"
                  value={config.date}
                  onChange={(e) => change({ date: e.target.value })}
                />
              </label>
              <label>
                Vehicle
                <select
                  value={config.vehicle}
                  onChange={(e) => change({ vehicle: e.target.value })}
                >
                  <option value="truck">Truck</option>
                  <option value="teryx">Teryx / side-by-side</option>
                </select>
              </label>
            </div>
            {config.vehicle === "teryx" && (
              <label>
                Actual vehicle width · inches
                <input
                  type="number"
                  min="30"
                  max="100"
                  value={config.vehicle_width_inches ?? ""}
                  placeholder="Unknown"
                  onChange={(e) =>
                    change({
                      vehicle_width_inches: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                />
                <small>
                  Check your vehicle's actual width. ATV permission is not
                  side-by-side permission. Complete drive-to-parking remains
                  conditional.
                </small>
              </label>
            )}
            <label>
              Mapped entry / assumed parking
              <select
                value={config.start_id}
                onChange={(e) => {
                  change({ start_id: e.target.value, custom_start: null });
                  setName(
                    (entries.find((v) => v.id === e.target.value)?.label ||
                      "TrailScout") + " scouting",
                  );
                }}
              >
                {!entries.some((e) => e.id === config.start_id) &&
                  config.start_id && (
                    <option value={config.start_id}>
                      Prior entry · currently unavailable
                    </option>
                  )}
                {entries.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.label}
                  </option>
                ))}
              </select>
            </label>
            {config.custom_start ? (
              <p className="micro">
                Custom start active: {config.custom_start.label} ·{" "}
                {config.custom_start.longitude.toFixed(6)},{" "}
                {config.custom_start.latitude.toFixed(6)}
              </p>
            ) : (
              <details className="entry-evidence">
                <summary>Entry evidence · parking conditional</summary>
                <p className="micro">
                  {entries.find((e) => e.id === config.start_id)?.note ||
                    "Entry evidence unavailable; retain this assumption for review."}
                </p>
              </details>
            )}
            <p className="search-scope">
              Search: {(config.corridor_m / 1000).toFixed(1)} km corridor +{" "}
              {config.search_envelope_m} m nearby.
              {config.travel_area && " Selected travel polygon active."}
              {config.target_area && " Separate target polygon active."}{" "}
              Advanced limits and Area & source tools adjust this area. Driving,
              parking and foot rights remain conditional.
            </p>
            <button
              className="primary compare"
              disabled={
                !area ||
                !ready ||
                !contextReady ||
                busy ||
                active ||
                (!config.start_id && !config.custom_start)
              }
              onClick={run}
            >
              {busy
                ? "Starting…"
                : dirty
                  ? "Recalculate comparison"
                  : "Compare route opportunities"}{" "}
              <span>↗</span>
            </button>
            {!contextReady && (
              <p className="micro" role="status">
                {contextFailed
                  ? "Entry/date evidence unavailable. Inputs are retained."
                  : "Checking entry and date evidence…"}{" "}
                {contextFailed && (
                  <button onClick={() => setContextRetry((n) => n + 1)}>
                    Retry entry evidence
                  </button>
                )}
              </p>
            )}
            {active && (
              <div className="job" role="status">
                <strong>{job?.stage}</strong>
                <p>{job?.message}</p>
                {job?.total > 0 ? (
                  <progress
                    aria-label="Backend work units"
                    max={job.total}
                    value={job.progress ?? 0}
                  />
                ) : (
                  <progress aria-label="Calculation running" />
                )}
                <button
                  disabled={job?.status === "cancelling"}
                  onClick={() =>
                    protectError(async () => {
                      await api("/jobs/" + job!.id + "/cancel", {});
                      setJob((j) => (j ? { ...j, status: "cancelling" } : j));
                    })
                  }
                >
                  {job?.status === "cancelling"
                    ? "Cancelling…"
                    : "Cancel calculation"}
                </button>
              </div>
            )}
            <p className="advanced-label">Advanced settings · optional</p>
            <details>
              <summary>Effort, optics & search limits</summary>
              <div className="detail-body">
                <p className="micro">{config.profile.explanation}</p>
                <NumberField
                  label="Flat pace · mph"
                  value={config.profile.pace_mph ?? 1.5}
                  onChange={(n) => profileChange("pace_mph", n)}
                  step={0.1}
                />
                <NumberField
                  label="Elapsed outing limit · hours"
                  value={config.profile.max_hours ?? 7}
                  onChange={(n) => profileChange("max_hours", n)}
                  step={0.5}
                />
                <NumberField
                  label="Movement reserve · fraction"
                  value={config.profile.reserve_fraction ?? 0.25}
                  onChange={(n) => profileChange("reserve_fraction", n)}
                  step={0.05}
                  max={0.6}
                />
                <NumberField
                  label="Conservative time multiplier"
                  value={config.profile.time_margin ?? 1.35}
                  onChange={(n) => profileChange("time_margin", n)}
                  step={0.05}
                />
                <NumberField
                  label="Condition time multiplier · dry=1"
                  value={config.profile.condition_factor ?? 1}
                  onChange={(n) => profileChange("condition_factor", n)}
                  step={0.1}
                />
                <NumberField
                  label="Off-trail round-trip miles limit"
                  value={config.profile.offtrail_miles ?? 0.25}
                  onChange={(n) => profileChange("offtrail_miles", n)}
                  step={0.05}
                />
                <NumberField
                  label="Off-trail round-trip minutes limit"
                  value={config.profile.offtrail_minutes ?? 35}
                  onChange={(n) => profileChange("offtrail_minutes", n)}
                  step={5}
                />
                <NumberField
                  label="Off-trail ground slope limit · °"
                  value={config.profile.max_offtrail_slope ?? 20}
                  onChange={(n) => profileChange("max_offtrail_slope", n)}
                  max={35}
                />
                <NumberField
                  label="Sustained walking grade limit · %"
                  value={(config.profile.max_route_grade ?? 0.3) * 100}
                  onChange={(n) => profileChange("max_route_grade", n / 100)}
                  max={80}
                />
                <NumberField
                  label="Steep travel allowance · metres"
                  value={config.profile.max_steep_m ?? 250}
                  onChange={(n) => profileChange("max_steep_m", n)}
                  step={50}
                />
                <NumberField
                  label="Steep grade band begins · %"
                  value={(config.profile.steep_grade ?? 0.15) * 100}
                  onChange={(n) => profileChange("steep_grade", n / 100)}
                  max={50}
                />
                <NumberField
                  label="Off-trail tree cover limit · %"
                  value={(config.profile.max_tree ?? 0.45) * 100}
                  onChange={(n) => profileChange("max_tree", n / 100)}
                  max={100}
                />
                <NumberField
                  label="Off-trail shrub cover limit · %"
                  value={(config.profile.max_shrub ?? 0.65) * 100}
                  onChange={(n) => profileChange("max_shrub", n / 100)}
                  max={100}
                />
                <NumberField
                  label="Viewing radius · metres"
                  value={config.view_radius_m}
                  onChange={(n) => change({ view_radius_m: n })}
                  step={250}
                  min={500}
                  max={3000}
                />
                <p className="micro">
                  16×50 stabilized binoculars, 77 mm scope & tripod. Radius is
                  an analysis assumption, not a detection or shooting guarantee.
                </p>
                <NumberField
                  label="Corridor radius from entry · metres"
                  value={config.corridor_m}
                  onChange={(n) => change({ corridor_m: n })}
                  step={500}
                  min={500}
                  max={4500}
                />
                <NumberField
                  label="Spur search envelope · metres"
                  value={config.search_envelope_m}
                  onChange={(n) => change({ search_envelope_m: n })}
                  step={100}
                  max={1500}
                />
                <p className="micro">
                  An outer search envelope, not a bushwhacking allowance. Every
                  proposed spur must fit its own distance, grade, cover and
                  return limits.
                </p>
                <NumberField
                  label="Viewpoint evaluation budget"
                  value={config.candidate_budget}
                  onChange={(n) => change({ candidate_budget: n })}
                  min={8}
                  max={80}
                />
              </div>
            </details>
            <PracticalPlanSettings
              value={config.practical_plan ?? null}
              ready={area?.practical?.status === "ready"}
              change={(practical_plan) => change({ practical_plan })}
            />
            <PracticalSettings
              value={config.practical ?? null}
              ready={area?.practical?.status === "ready"}
              change={(practical) => change({ practical })}
            />
            <details>
              <summary>Observation windows & dark travel</summary>
              <div className="detail-body">
                <p className="micro">
                  Local astronomical sunrise/sunset anchor the windows. Mountain
                  shadows and legal shooting hours are separate.
                </p>
                <NumberField
                  label="AM begins · minutes from sunrise"
                  value={config.schedule.am_start_offset ?? 0}
                  onChange={(n) => scheduleChange("am_start_offset", n)}
                  min={-360}
                />
                <NumberField
                  label="AM ends · minutes from sunrise"
                  value={config.schedule.am_end_offset ?? 180}
                  onChange={(n) => scheduleChange("am_end_offset", n)}
                  min={-360}
                />
                <NumberField
                  label="PM begins · minutes from sunset"
                  value={config.schedule.pm_start_offset ?? -180}
                  onChange={(n) => scheduleChange("pm_start_offset", n)}
                  min={-360}
                />
                <NumberField
                  label="PM ends · minutes from sunset"
                  value={config.schedule.pm_end_offset ?? 0}
                  onChange={(n) => scheduleChange("pm_end_offset", n)}
                  min={-360}
                />
                <NumberField
                  label="Minimum observation · minutes/stop"
                  value={config.schedule.min_glassing_minutes ?? 60}
                  onChange={(n) => scheduleChange("min_glassing_minutes", n)}
                  min={15}
                />
                <NumberField
                  label="Setup allowance · minutes/stop"
                  value={config.schedule.setup_minutes ?? 15}
                  onChange={(n) => scheduleChange("setup_minutes", n)}
                />
                <NumberField
                  label="Break allowance · minutes"
                  value={config.schedule.break_minutes ?? 20}
                  onChange={(n) => scheduleChange("break_minutes", n)}
                />
                <label>
                  Earliest departure · local
                  <input
                    type="time"
                    value={config.schedule.earliest || "04:00"}
                    onChange={(e) => scheduleChange("earliest", e.target.value)}
                  />
                </label>
                <label>
                  Latest return · local
                  <input
                    type="time"
                    value={config.schedule.latest || "21:00"}
                    onChange={(e) => scheduleChange("latest", e.target.value)}
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={config.schedule.dark_travel || false}
                    onChange={(e) =>
                      scheduleChange("dark_travel", e.target.checked)
                    }
                  />
                  Allow travel before/after civil twilight
                </label>
              </div>
            </details>
            <details>
              <summary>Access assumptions & owner edits</summary>
              <div className="detail-body">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={config.explore_unknown}
                    onChange={(e) =>
                      change({ explore_unknown: e.target.checked })
                    }
                  />
                  Explore unknown foot access as a scenario
                </label>
                <p className="micro">
                  Unknown is never verified permission. Motor-closed roads need
                  supported foot-use evidence or this explicit scenario.
                </p>
                <div className="edit-count">
                  {config.pinned.length} pinned · {config.rejected.length}{" "}
                  rejected · {config.excluded_segments.length} segments excluded
                  · {config.excluded_areas.length} areas excluded
                </div>
                <button
                  onClick={() => {
                    setEditMode(editMode === "pin" ? "" : "pin");
                    editCorner.current = null;
                  }}
                >
                  Pin a new map viewpoint
                </button>
                <button
                  onClick={() => {
                    setEditMode(editMode === "exclude" ? "" : "exclude");
                    editCorner.current = null;
                  }}
                >
                  Exclude a small map area
                </button>
                <button
                  onClick={() =>
                    change({
                      pinned: [],
                      rejected: [],
                      excluded_segments: [],
                      excluded_areas: [],
                      restrictions: [],
                      custom_start: null,
                    })
                  }
                >
                  Clear owner overrides
                </button>
                <p className="micro">
                  Click a mapped segment to exclude it, record a dated access
                  status, or choose an intended start. New points get fresh
                  visibility calculations.
                </p>
                <label>
                  Custom start · longitude, latitude, segment ID
                  <textarea
                    rows={3}
                    aria-label="Custom start JSON"
                    placeholder='{"longitude":-107.3,"latitude":38.66,"segment":"trails:…:0"}'
                    onBlur={(e) => {
                      if (e.target.value)
                        try {
                          change({ custom_start: JSON.parse(e.target.value) });
                        } catch {
                          setError(
                            "Custom start must be JSON with longitude, latitude and segment.",
                          );
                        }
                    }}
                  />
                </label>
              </div>
            </details>
          </fieldset>
        </aside>
        <main data-analysis-id={result?.analysis_id || ""}>
          <div className="main-heading">
            <div>
              <div className="eyebrow">
                {result
                  ? result.start.label.toUpperCase()
                  : "GMU 54 · SECOND RIFLE CONTEXT"}
              </div>
              <h2>
                {result
                  ? "Choose a view. Review the return."
                  : "Entry, effort, then a useful view."}
              </h2>
            </div>
            <span className="pill">
              {dirty
                ? "INPUTS CHANGED"
                : result
                  ? result.settings.explore_unknown
                    ? "UNKNOWN FOOT ACCESS SCENARIO"
                    : "PREVIEW COMPARISON"
                  : area
                    ? "PREPARED LOCAL DATA"
                    : "CHECK LOCAL SOURCES"}
            </span>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
              <button onClick={() => setError("")} aria-label="Dismiss error">
                ×
              </button>
            </div>
          )}
          {!sourcesLoading && !area && (
            <div className="error" role="alert">
              Core package unavailable. Saved versions remain below. Review
              local sources and preparation details; no analysis can run until
              the core package is ready.{" "}
              <button onClick={() => location.reload()}>
                Retry local sources
              </button>
            </div>
          )}
          {job &&
            ["failed", "cancelled", "interrupted"].includes(job.status) &&
            !active && (
              <div className="notice" role="status">
                Last calculation {job.status}. Inputs and previous preview are
                retained.{" "}
                <button disabled={!area || !contextReady || busy} onClick={run}>
                  Retry calculation
                </button>
              </div>
            )}
          {notice && (
            <div className="notice" role="status">
              {notice}
            </div>
          )}
          {result && (
            <Recommendation
              result={result}
              option={option}
              mode={mode}
              stale={previewStale}
              pending={active}
              onMode={selectMode}
              onSelect={selectOption}
              onInspect={inspect}
              onSave={() => {
                saveRef.current
                  ?.querySelector("input")
                  ?.focus({ preventScroll: true });
                saveRef.current?.scrollIntoView({ block: "start" });
              }}
            />
          )}
          <ScoutMap
            mode={mode}
            excludedAreas={config.excluded_areas}
            context={context}
            result={result}
            option={option}
            starts={entries}
            onSegment={setSegment}
            onPoint={(p) => {
              setPoint(
                result?.candidates.find((v: RecordValue) => v.id === p.id) ||
                  null,
              );
              setSegment(null);
            }}
            onMapPoint={mapPoint}
            editMode={editMode}
            profilePoint={profilePoint}
          />
          {!result && (
            <div className="empty">
              <strong>Real sources. Bounded comparisons.</strong>
              <p>
                Choose your entry and compare connected trail portions and new
                nearby viewpoints. Travel includes the complete return. No
                historical glassing points are required.
              </p>
              <div className="empty-stats">
                <span>
                  10 m<small>terrain profiles</small>
                </span>
                <span>
                  2023<small>annual vegetation</small>
                </span>
                <span>
                  25%<small>default reserve</small>
                </span>
              </div>
            </div>
          )}
          {segment && (
            <section className="selected-evidence">
              <button className="close" onClick={() => setSegment(null)}>
                ×
              </button>
              <h3>{segment.name}</h3>
              <code>{segment.id}</code>
              <p>
                {typeof segment.access === "string"
                  ? segment.access
                  : JSON.stringify(segment.access)}
              </p>
              <button
                onClick={() =>
                  protectError(async () => {
                    const start = await api("/start-preview", {
                      segment: segment.id,
                      longitude: segment.click_longitude,
                      latitude: segment.click_latitude,
                    });
                    change({ custom_start: start });
                    setNotice(
                      "Start set on the intended segment; click offset " +
                        start.click_offset_m.toFixed(1) +
                        " m. Parking and vehicle approach remain unverified. Recalculate.",
                    );
                  })
                }
              >
                Use clicked position as start
              </button>
              <button
                onClick={() =>
                  change({
                    excluded_segments: [
                      ...new Set([...config.excluded_segments, segment.id]),
                    ],
                  })
                }
              >
                Exclude this segment
              </button>
              <label>
                Dated status evidence
                <input
                  placeholder="e.g. GMUG order URL / owner report and date"
                  value={manualNote}
                  onChange={(e) => setManualNote(e.target.value)}
                />
              </label>
              <div className="button-row">
                {["supported", "unknown", "closed"].map((status) => (
                  <button
                    key={status}
                    disabled={!manualNote}
                    onClick={() =>
                      change({
                        restrictions: [
                          ...config.restrictions,
                          {
                            segment: segment.id,
                            from: config.date,
                            until: config.date,
                            foot: status,
                            provenance: manualNote,
                          },
                        ],
                      })
                    }
                  >
                    Foot: {status}
                  </button>
                ))}
              </div>
              <p className="micro">
                To change the intended start, copy this segment ID into Custom
                start JSON with a coordinate on the actual line. No crossing or
                nearby parallel line is automatically connected.
              </p>
            </section>
          )}
          {point && (
            <section className="selected-evidence">
              <button className="close" onClick={() => setPoint(null)}>
                ×
              </button>
              <h3>Viewpoint {point.id.slice(0, 6)}</h3>
              <p>
                {point.longitude.toFixed(7)}, {point.latitude.toFixed(7)} ·{" "}
                {point.kind}
              </p>
              <p>{point.standing_note}</p>
              <button onClick={() => pin(point)}>Pin this viewpoint</button>
              <button
                onClick={() =>
                  change({
                    rejected: [...new Set([...config.rejected, point.id])],
                    pinned: config.pinned.filter(
                      (v: RecordValue) =>
                        Math.abs(v.longitude - point.longitude) > 1e-8 ||
                        Math.abs(v.latitude - point.latitude) > 1e-8,
                    ),
                  })
                }
              >
                Reject this viewpoint
              </button>
            </section>
          )}
          {result && (
            <>
              <div className="results-heading">
                <h3>
                  {result.options.length}{" "}
                  {result.settings.explore_unknown ? "scenario" : "supported"}{" "}
                  route previews
                </h3>
                <span>
                  {result.search.evaluated} exact positions evaluated ·{" "}
                  {result.search.corridor_radius_m / 1000} km corridor
                </span>
              </div>
              {result.empty_reason && (
                <div className="error">
                  {result.empty_reason}
                  {result.pin_errors.map((p: RecordValue) => (
                    <p key={p.id}>
                      Pinned {p.id.slice(0, 6)}: {p.reasons.join("; ")}
                    </p>
                  ))}
                </div>
              )}
              {result.practical && (
                <PracticalResult review={result.practical} />
              )}
              <div className="result-grid">
                <details className="all-previews">
                  <summary>
                    All retained route previews ({result.options.length})
                  </summary>
                  <div className="options" aria-label="Route alternatives">
                    {result.options.map((o: RecordValue) => (
                      <button
                        className={
                          "option " + (o.id === selected ? "selected" : "")
                        }
                        key={o.id}
                        aria-pressed={o.id === selected}
                        onClick={() => selectOption(o.id)}
                      >
                        <div className="option-top">
                          <strong>
                            {o.viewpoints.length === 1
                              ? "Stay at one view"
                              : "Connected viewpoints"}
                          </strong>
                          {result.recommended[mode] === o.id && (
                            <span className="recommended">RECOMMENDED</span>
                          )}
                        </div>
                        <div className="option-number">
                          {result.practical_plan
                            ? Math.round(
                                o.schedules[mode]?.practical?.relative_m2 ?? 0,
                              ).toLocaleString()
                            : acres(o.coverage.effective_m2)}{" "}
                          <small>
                            {result.practical_plan
                              ? "relative-index m² · practical"
                              : "quality-adjusted acre equivalents"}
                          </small>
                        </div>
                        <div className="option-metrics">
                          <span>{miles(o.movement.distance_m)} mi</span>
                          <span>↑ {feet(o.movement.ascent_m)} ft</span>
                          <span>
                            {o.movement.hours_high.toFixed(1)} h travel
                          </span>
                        </div>
                        <p>
                          {o.viewpoints.length}{" "}
                          {o.viewpoints.length === 1
                            ? "glassing location"
                            : "locations"}{" "}
                          ·{" "}
                          {o.schedules[mode]?.feasible
                            ? "Fits " + mode.toUpperCase()
                            : "Does not fit " + mode.toUpperCase()}
                        </p>
                      </button>
                    ))}
                  </div>
                </details>
                {option && (
                  <section
                    className="route-detail"
                    ref={inspectionRef}
                    tabIndex={-1}
                    aria-label="Selected route inspection"
                  >
                    <TimedResult option={option} mode={mode} />
                    <div
                      className="tabs"
                      role="group"
                      aria-label="Inspection views"
                    >
                      {[
                        "route",
                        "schedule",
                        "coverage",
                        "access",
                        "marginal",
                      ].map((t) => (
                        <button
                          key={t}
                          aria-pressed={tab === t}
                          onClick={() => setTab(t)}
                          className={tab === t ? "active" : ""}
                        >
                          {t[0].toUpperCase() + t.slice(1)}
                        </button>
                      ))}
                    </div>
                    {tab === "route" && (
                      <>
                        <div className="metric-grid">
                          <div>
                            <strong>
                              {miles(option.movement.distance_m)}{" "}
                              <small>mi</small>
                            </strong>
                            <span>full traveled distance</span>
                          </div>
                          <div>
                            <strong>
                              {feet(option.movement.ascent_m)} <small>ft</small>
                            </strong>
                            <span>cumulative ascent</span>
                          </div>
                          <div>
                            <strong>
                              {option.movement.hours_low.toFixed(1)}–
                              {option.movement.hours_high.toFixed(1)}{" "}
                              <small>h</small>
                            </strong>
                            <span>movement time range</span>
                          </div>
                          <div>
                            <strong>
                              {miles(option.movement.offtrail_m)}{" "}
                              <small>mi</small>
                            </strong>
                            <span>actual off-trail travel</span>
                          </div>
                        </div>
                        <div className="profile-heading">
                          <h4>Elevation · every traveled leg</h4>
                          <span>Hover to locate a section</span>
                        </div>
                        <svg
                          className="profile"
                          viewBox="0 0 800 130"
                          preserveAspectRatio="none"
                          onMouseMove={profileHover}
                          onMouseLeave={() => setProfilePoint(null)}
                          aria-label="Linked route elevation profile"
                        >
                          <path
                            d={profilePath()}
                            stroke="#315d4e"
                            fill="none"
                            strokeWidth="2"
                          />
                        </svg>
                        <p className="micro">
                          {profilePoint
                            ? `${feet(profilePoint.elevation_m)} ft elevation · raw ${feet(profilePoint.raw_elevation_m)} ft`
                            : "20 m profile sampling over 10 m terrain; raw evidence retained. Median + 1.5 m vertical-error simplification controls noise."}
                        </p>
                        <div className="return-box">
                          <strong>Your return is already included</strong>
                          <span>
                            {miles(option.legs.at(-1).distance_m)} mi · ↑
                            {feet(option.legs.at(-1).ascent_m)} / ↓
                            {feet(option.legs.at(-1).descent_m)} ft ·{" "}
                            {option.legs.at(-1).hours_low.toFixed(1)}–
                            {option.legs.at(-1).hours_high.toFixed(1)} h
                          </span>
                        </div>
                        <p className="micro">
                          After the complete return:{" "}
                          {miles(option.remaining.usable_distance_m)} usable
                          miles and {feet(option.remaining.usable_ascent_m)} ft
                          ascent remain, with{" "}
                          {miles(option.remaining.held_distance_m)} mi /{" "}
                          {feet(option.remaining.held_ascent_m)} ft still held
                          as reserve.
                        </p>
                        <p>
                          Longest sustained climb:{" "}
                          {feet(option.movement.longest_climb_m)} ft. Sustained
                          steep travel:{" "}
                          {Math.round(option.movement.sustained_steep_m)} m.
                        </p>
                        <details>
                          <summary>Difficult sections & grade evidence</summary>
                          {option.legs.map((l: RecordValue, i: number) => (
                            <div key={i}>
                              <h4>Leg {i + 1}</h4>
                              <p>
                                {feet(l.ascent_m)} ft ascent /{" "}
                                {feet(l.descent_m)} ft descent ·{" "}
                                {Math.round(l.unknown_cover_m)} m cover unknown.
                                Surrounding hillside max{" "}
                                {Math.round(l.max_surrounding_ground_slope_deg)}
                                °; {Math.round(l.mapped_steep_hillside_m)}{" "}
                                mapped metres cross ground steeper than 25°.
                                This is separate from walking grade;
                                tread/exposure remains unverified.
                              </p>
                              {Object.entries(l.grade_bands_m).map(([k, v]) => (
                                <span className="band" key={k}>
                                  {k}: {Math.round(v as number)} m
                                </span>
                              ))}
                              {l.steep_sections.map(
                                (s: RecordValue, n: number) => (
                                  <p key={n}>
                                    {s.direction} · {Math.round(s.start_m)}–
                                    {Math.round(s.end_m)} m ·{" "}
                                    {Math.round(s.grade * 100)}% sustained
                                  </p>
                                ),
                              )}
                            </div>
                          ))}
                        </details>
                        <h4>Glassing positions</h4>
                        {option.viewpoints.map((p: RecordValue) => (
                          <div className="viewpoint" key={p.id}>
                            <button onClick={() => setPoint(p)}>
                              {p.id.slice(0, 6)} · {p.kind} ↗
                            </button>
                            <small>
                              {p.longitude.toFixed(7)}, {p.latitude.toFixed(7)}
                            </small>
                            <p>{p.standing_note}</p>
                          </div>
                        ))}
                      </>
                    )}
                    {tab === "schedule" && (
                      <section
                        ref={scheduleRef}
                        tabIndex={-1}
                        aria-label="Selected schedule"
                      >
                        <div className="schedule-modes">
                          {[
                            ["am", "Morning"],
                            ["pm", "Evening"],
                            ["combined", "AM + PM trips"],
                            ["stay", "Stay all day"],
                          ].map(([v, label]) => (
                            <button
                              className={mode === v ? "active" : ""}
                              onClick={() => selectMode(v)}
                              key={v}
                              disabled={
                                !!result?.practical_plan &&
                                ["combined", "stay"].includes(v)
                              }
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                        {currentSchedule ? (
                          <>
                            <div
                              className={
                                currentSchedule.feasible ? "fits" : "not-fit"
                              }
                            >
                              {currentSchedule.feasible
                                ? "Fits conservative arrival, observation and return checks"
                                : "This time variant is not feasible"}
                            </div>
                            {currentSchedule.reasons.map((r: string) => (
                              <p className="micro" key={r}>
                                {r}
                              </p>
                            ))}
                            <p>{currentSchedule.description}</p>
                            <p className="micro">
                              America/Denver · {result.settings.date} ·{" "}
                              {currentSchedule.clock_hours.toFixed(1)} elapsed
                              hours. Glassing, setup and breaks consume clock
                              time.
                            </p>
                            {currentSchedule.events.map(
                              (e: RecordValue, i: number) => (
                                <div className="event" key={i}>
                                  <span className="event-dot" />
                                  <div>
                                    <strong>
                                      {e.kind === "observe"
                                        ? "Glassing · stop " + (e.stop + 1)
                                        : e.kind[0].toUpperCase() +
                                          e.kind.slice(1)}
                                    </strong>
                                    <p>
                                      {e.kind === "outbound"
                                        ? `${clock(e.depart)} → ${clock(e.arrival_range[0])}–${clock(e.arrival_range[1])}`
                                        : e.kind === "observe"
                                          ? `${clock(e.start)}–${clock(e.end)} · ${Math.round(e.minutes)} min`
                                          : e.kind === "break"
                                            ? `${clock(e.start)} · ${Math.round(e.minutes)} min`
                                            : `${clock(e.depart)} → ${clock(e.arrival)}`}
                                    </p>
                                  </div>
                                </div>
                              ),
                            )}
                            {currentSchedule.latest_leave_viewpoint && (
                              <div className="return-box">
                                <strong>
                                  Leave the viewpoint by{" "}
                                  {clock(
                                    currentSchedule.latest_leave_viewpoint,
                                  )}
                                </strong>
                                <span>
                                  Includes break and conservative return
                                  allowance.
                                </span>
                              </div>
                            )}
                            <p className="micro">
                              The observation window is not a legal
                              shooting-hours calculation. Verify current CPW
                              rules and GMUG restrictions.
                            </p>
                          </>
                        ) : (
                          <p>
                            Stay-all-day scheduling is available for a
                            one-location plan.
                          </p>
                        )}
                      </section>
                    )}
                    {tab === "coverage" && (
                      <>
                        <h4>Unique coverage, counted once</h4>
                        <div className="metric-grid">
                          <div>
                            <strong>
                              {acres(option.coverage.matching_m2)}
                            </strong>
                            <span>physical matching acres</span>
                          </div>
                          <div>
                            <strong>
                              {acres(option.coverage.effective_m2)}
                            </strong>
                            <span>quality-adjusted equivalents</span>
                          </div>
                          <div>
                            <strong>{acres(option.coverage.unknown_m2)}</strong>
                            <span>habitat/context unknown acres</span>
                          </div>
                          <div>
                            <strong>
                              {acres(option.coverage.priority_m2)}
                            </strong>
                            <span>priority visible acres</span>
                          </div>
                        </div>
                        <p>
                          Quality-adjusted coverage integrates visible eligible
                          cell area × habitat preference × vegetation
                          glassability. Overlapping views count each aligned
                          cell once.
                        </p>
                        <p className="micro">
                          Not literal acreage searched, deer density, encounter
                          probability or assured optical clearance. Repeated
                          viewing in AM/PM does not create new unique acreage.
                        </p>
                        {option.contributions.map((v: RecordValue) => (
                          <div className="viewpoint" key={v.id}>
                            <strong>{v.id.slice(0, 6)}</strong>
                            <p>
                              Added at inclusion:{" "}
                              {acres(v.inclusion_effective_m2)} equivalents.
                              <br />
                              Exclusive in final collection:{" "}
                              {acres(v.final_exclusive_effective_m2)}{" "}
                              equivalents.
                            </p>
                          </div>
                        ))}
                      </>
                    )}
                    {tab === "access" && (
                      <>
                        <h4>Competing access evidence</h4>
                        {option.viewpoints.map((p: RecordValue) => (
                          <div className="viewpoint" key={p.id}>
                            <strong>
                              {p.id.slice(0, 6)} · {p.access.label}
                            </strong>
                            <p>
                              Nearest date/mode-supported motor route:{" "}
                              {p.access.nearest_motor_m === null
                                ? "unknown"
                                : Math.round(p.access.nearest_motor_m) +
                                  " m"}{" "}
                              · {p.access.motor_name || "unnamed"}.
                            </p>
                            <p>
                              Other plausible entry:{" "}
                              {p.access.other_entry || "not supported"} ·{" "}
                              {p.access.other_entry_straight_m === null
                                ? "unknown"
                                : miles(p.access.other_entry_straight_m) +
                                  " mi straight-line lower bound"}
                              .
                            </p>
                            <p>
                              {acres(p.access.target_near_motor_m2)} visible
                              target acres within 500 m of supported mapped
                              motor routes.
                            </p>
                            {p.access.connected_other_access ? (
                              <p>
                                Connected other entry:{" "}
                                {p.access.connected_other_access.entry};{" "}
                                {miles(
                                  p.access.connected_other_access
                                    .walking_distance_m,
                                )}{" "}
                                mi /{" "}
                                {p.access.connected_other_access.walking_hours_high.toFixed(
                                  1,
                                )}{" "}
                                conservative walking hours. Shared selected
                                approach:{" "}
                                {Math.round(
                                  p.access.connected_other_access
                                    .shared_selected_approach_m,
                                )}{" "}
                                m. {p.access.connected_other_access.assumption}
                              </p>
                            ) : (
                              <p className="micro">
                                No other entry has a supported connection in
                                this bounded graph; that is missing evidence,
                                not solitude.
                              </p>
                            )}
                            <p className="micro">{p.access.definition}</p>
                            <p className="micro">{p.access.completeness}</p>
                          </div>
                        ))}
                        <p>
                          No hunter-count, solitude or encounter probability is
                          predicted. Easy or vehicle-closed routes may attract
                          pedestrians.
                        </p>
                      </>
                    )}
                    {tab === "marginal" && (
                      <>
                        <h4>When does more walking add little?</h4>
                        <p className="micro">
                          Every variant includes its return. These are evaluated
                          choices, not a proven optimum or a statistical
                          stopping point.
                        </p>
                        <div
                          className="table-scroll"
                          style={{ maxHeight: "28rem", overflow: "auto" }}
                        >
                          <table>
                            <thead>
                              <tr>
                                <th>Variant</th>
                                <th>Travel h</th>
                                <th>Gain ft</th>
                                <th>
                                  {result.practical_plan
                                    ? "Practical relative-index m²"
                                    : "Useful equivalents"}
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {[...result.marginal]
                                .sort((a, b) => a.hours_high - b.hours_high)
                                .map((v: RecordValue) => (
                                  <tr
                                    key={v.id}
                                    className={
                                      v.id === selected ? "selected-row" : ""
                                    }
                                  >
                                    <td>
                                      {v.id.slice(0, 6)}
                                      {v.dominated ? " · dominated" : ""}
                                    </td>
                                    <td>{v.hours_high.toFixed(2)}</td>
                                    <td>{feet(v.ascent_m)}</td>
                                    <td>
                                      {result.practical_plan
                                        ? v.modes[mode]?.relative_m2 === null ||
                                          v.modes[mode]?.relative_m2 ===
                                            undefined
                                          ? "Unavailable"
                                          : Math.round(
                                              v.modes[mode].relative_m2,
                                            ).toLocaleString()
                                        : acres(v.effective_m2)}
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        </div>
                        <p>{result.recommendation_method}</p>
                      </>
                    )}
                    <div className="save-box" ref={saveRef}>
                      <label>
                        Plan name
                        <input
                          value={name}
                          onChange={(e) => {
                            openRevision.current++;
                            setName(e.target.value);
                          }}
                        />
                      </label>
                      <label>
                        Time variant
                        <select
                          aria-label="Time variant"
                          value={mode}
                          onChange={(e) => selectMode(e.target.value)}
                        >
                          <option value="am">Morning</option>
                          <option value="pm">Evening</option>
                          <option
                            disabled={!!result?.practical_plan}
                            value="combined"
                          >
                            AM + PM trips
                          </option>
                          <option
                            disabled={!!result?.practical_plan}
                            value="stay"
                          >
                            Stay all day · one location
                          </option>
                        </select>
                      </label>
                      <button
                        className="primary"
                        disabled={
                          previewStale ||
                          busy ||
                          active ||
                          !currentSchedule?.feasible
                        }
                        onClick={() => protectError(save)}
                      >
                        {savedPlan ? "Save a new version" : "Save this plan"}
                      </button>
                      {!currentSchedule?.feasible && (
                        <p className="micro">
                          {currentSchedule?.reasons.join("; ") ||
                            "This time variant is unavailable for this route."}
                        </p>
                      )}
                      {previewStale && (
                        <p className="micro">
                          Recalculate edited inputs before saving.
                        </p>
                      )}
                      {savedPlan && (
                        <button
                          onClick={() => {
                            setSavedPlan(null);
                            setNotice(
                              "Saving will create a separate plan. The previously opened plan and its history are preserved.",
                            );
                          }}
                        >
                          Save as a separate plan
                        </button>
                      )}
                      {savedPlan && (
                        <div className="saved-exports">
                          <p>
                            Exports: immutable <strong>{savedPlan.name}</strong>{" "}
                            · {savedPlan.mode.toUpperCase()} · version{" "}
                            {savedPlan.id.slice(0, 8)}. Changing the preview
                            does not change these files.
                          </p>
                          <div className="exports" aria-label="Plan exports">
                            {["md", "json", "gpx", "geojson"].map((k) => (
                              <a
                                key={k}
                                href={
                                  "/api/plans/" + savedPlan.id + "/export/" + k
                                }
                                download
                              >
                                {k === "md" ? "Field summary" : k.toUpperCase()}{" "}
                                ↓
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </section>
                )}
              </div>
              <details className="evaluation">
                <summary>
                  All evaluated viewpoints & explanations (
                  {result.candidates.length})
                </summary>
                {result.candidates.map((p: RecordValue) => (
                  <div className="candidate-row" key={p.id}>
                    <button onClick={() => setPoint(p)}>
                      {p.id.slice(0, 6)} · {p.kind}
                    </button>
                    <span>
                      {p.feasible
                        ? acres(p.coverage.effective_m2) + " useful equivalents"
                        : p.reasons.join("; ")}
                    </span>
                  </div>
                ))}
              </details>
            </>
          )}
          <section className="saved-section">
            <div className="results-heading">
              <h3>Saved plans & versions</h3>
              <span>Immutable history · local to TrailScout</span>
            </div>
            {saved.length === 0 ? (
              <p className="micro">
                Previews appear above; only the choices you save become plans.
              </p>
            ) : (
              <div className="saved-list">
                {saved.map((p) => (
                  <div className="saved-card" key={p.id}>
                    <button
                      disabled={active || busy || !ready}
                      onClick={() => protectError(() => openSaved(p.id))}
                    >
                      <strong>{p.name}</strong>
                      <small>
                        {p.mode?.toUpperCase()} ·{" "}
                        {new Date(p.created_utc).toLocaleString()} ·{" "}
                        {p.id.slice(0, 8)}
                      </small>
                    </button>
                    <button
                      onClick={() =>
                        protectError(async () => {
                          const v = await api("/plans/" + p.id);
                          setCompareSaved((c) =>
                            [...c.filter((x) => x.id !== v.id), v].slice(-4),
                          );
                        })
                      }
                    >
                      Compare
                    </button>
                  </div>
                ))}
              </div>
            )}
            {compareSaved.length > 0 && (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Saved outing</th>
                      <th>Entry</th>
                      <th>Miles / gain</th>
                      <th>Established equivalents</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compareSaved.map((p) => (
                      <tr key={p.id}>
                        <td>{p.name}</td>
                        <td>{p.start.label}</td>
                        <td>
                          {miles(p.option.movement.distance_m)} mi /{" "}
                          {feet(p.option.movement.ascent_m)} ft
                        </td>
                        <td>
                          {acres(p.option.coverage.effective_m2)}
                          <small>
                            {p.source_revision ===
                            compareSaved[0].source_revision
                              ? "same source revision"
                              : "different sources; not directly comparable"}
                          </small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <details className="history">
            <summary>Calculation history & recovery</summary>
            {history.map((j) => (
              <div className="history-row" key={j.id}>
                <span>
                  {j.status} · {j.created_utc}
                  <small>{j.error || j.message}</small>
                </span>
                {j.status === "completed" && j.kind !== "prepare" ? (
                  <button
                    disabled={active || busy || !ready}
                    onClick={() =>
                      protectError(() => openPreview(j.analysis_id))
                    }
                  >
                    Open preview
                  </button>
                ) : !active && j.kind === "prepare" ? (
                  <button
                    onClick={() =>
                      protectError(async () => {
                        const next = await api("/sources/prepare", {
                          ...j.settings,
                          resume_id: j.id,
                        });
                        jobRef.current = next.id;
                        setJob(next);
                      })
                    }
                  >
                    Retry preparation
                  </button>
                ) : (
                  !active && (
                    <button
                      onClick={() => {
                        editRevision.current++;
                        openRevision.current++;
                        setConfig(j.settings);
                        setDirty(true);
                        setNotice(
                          "Inputs restored. Compare to retry; completed compatible artifacts are reused.",
                        );
                      }}
                    >
                      Restore inputs / retry
                    </button>
                  )
                )}
              </div>
            ))}
          </details>
          <details className="sources">
            <summary>Sources, coverage limits & bounded preparation</summary>
            {area && (
              <>
                <p>{area.note}</p>
                <p>
                  Terrain: {area.diagnostics.dem.resolution_m} m,{" "}
                  {area.diagnostics.dem.crs}, vertical metres / NAVD88; no
                  vertical correction. Vegetation: 2023 fractional cover, 40 m
                  conservative context support. {area.network_count} attributed
                  network features.
                </p>
                <p>
                  Unit bounds:{" "}
                  {area.bounds.map((n: number) => n.toFixed(5)).join(", ")}.
                  Terrain/access buffers extend beyond the hunting target
                  boundary.
                </p>
                <p>
                  Budgets: 2 million 10 m terrain cells; 8–80 viewpoints; one
                  worker; 250 MiB acquisition ceiling; 2 GiB derived-state
                  ceiling; 20 GiB free reserve.
                </p>
              </>
            )}
            <div className="source-links">
              <a
                href="https://www.fs.usda.gov/r02/gmug"
                target="_blank"
                rel="noreferrer"
              >
                GMUG conditions & alerts ↗
              </a>
              <a
                href="https://cpw.state.co.us/hunting/big-game"
                target="_blank"
                rel="noreferrer"
              >
                CPW rules to verify ↗
              </a>
            </div>
            <p className="micro">
              Prepared terrain supports other bounded corridors: choose another
              entry or a start on an intended mapped segment. Import a
              travel/target/exclusion polygon below; bounds and obstruction
              support are validated before analysis.
            </p>
            <label>
              WGS84 GeoJSON polygon / attributed network
              <textarea
                aria-label="Source GeoJSON"
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                rows={4}
              />
            </label>
            <div className="button-row">
              {[
                ["travel_area", "Use as travel area"],
                ["target_area", "Use as target area"],
              ].map(([k, label]) => (
                <button
                  key={k}
                  onClick={() => {
                    try {
                      const g = JSON.parse(importText);
                      change({ [k]: g.geometry || g });
                    } catch {
                      setError("Enter a valid GeoJSON Polygon or Feature.");
                    }
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="micro">
              Network imports preserve original attributes and dated provenance
              in TrailScout only.
            </p>
            <label>
              Network source kind
              <select
                value={sourceKind}
                onChange={(e) => setSourceKind(e.target.value)}
              >
                <option value="closed_roads">Motor-closed roads</option>
                <option value="mvum_roads">MVUM roads</option>
                <option value="mvum_trails">MVUM trails</option>
              </select>
            </label>
            <label>
              Source date
              <input
                type="date"
                value={sourceDate}
                onChange={(e) => setSourceDate(e.target.value)}
              />
            </label>
            <label>
              Provenance / source URL
              <input
                value={manualNote}
                onChange={(e) => setManualNote(e.target.value)}
              />
            </label>
            <button
              disabled={active || !manualNote}
              onClick={() =>
                protectError(async () => {
                  await api("/sources/import", {
                    kind: sourceKind,
                    geojson: JSON.parse(importText),
                    source_date: sourceDate,
                    provenance: manualNote,
                  });
                  setArea((await api("/areas"))[0]);
                  setDirty(true);
                  setNotice(
                    "Imported a new immutable attributed source. Recalculate affected plans.",
                  );
                })
              }
            >
              Validate & import network snapshot
            </button>
            <button
              disabled={active}
              onClick={() =>
                protectError(async () => {
                  const start =
                    config.custom_start ||
                    entries.find((e) => e.id === config.start_id);
                  if (!start) throw new Error("Choose an entry first");
                  const j = await api("/sources/prepare", {
                    longitude: start.longitude,
                    latitude: start.latitude,
                    radius_m: 5000,
                  });
                  jobRef.current = j.id;
                  setJob(j);
                })
              }
            >
              Prepare fresh official access · 5 km around entry
            </button>
            <p className="micro">
              Fetches bounded USFS motor-closed and MVUM road/trail snapshots,
              with metadata and count checks. Requires connectivity;
              failed/cancelled pieces remain inspectable. Existing prepared
              plans remain usable offline.
            </p>
          </details>
        </main>
      </div>
      <footer>
        TRAILSCOUT · Best supported among evaluated choices. Terrain
        opportunity, effort and access evidence stay separate.
      </footer>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
