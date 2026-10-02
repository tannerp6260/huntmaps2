import { useEffect, useRef, useState } from 'react';
type Lesson = 'review' | 'area';
type Progress = { lesson: Lesson; step: string; paused: boolean; complete: boolean };
type Notes = Record<string, Record<string, { status: string; notes: string }>>;
const key = 'huntmaps-training-v2';
const reviewSteps = [
  {
    id: 'select',
    title: 'Select a setup on the left',
    text: 'We’ve opened the completed Soap Creek example for you. No prior run is needed. In the Observer setups cards on the LEFT, click A0075. Its coordinates and terrain-visible area appear in the details panel on the RIGHT.',
    target: 'setup-A0075',
    extra:
      'The colored cells mark target ground terrain permits you to see from this observer. Trees and branches can still block your actual view.',
  },
  {
    id: 'compare',
    title: 'Check Compare in the observer cards',
    text: 'In the Observer setups cards on the LEFT, check the Compare boxes for A0075, V010 and V008. Read the three colored names above the map.',
    target: 'observer-list',
    extra:
      'These are saved alternative observer locations in one neighborhood. Each colored layer keeps its own visible ground. Shared terrain is overlap, not extra acreage. The tool does not choose an optimal setup or route.',
  },
  {
    id: 'separate',
    title: 'Toggle a view above the map',
    text: 'Use the Compare individual saved views panel at the TOP OF THE MAP. Uncheck the box beside V010, then check it again. Leave the Compare boxes in the left-hand observer cards selected.',
    target: 'view-switches',
    extra:
      'This hides only V010’s map overlay. V010 stays in the comparison. Look for ground that only one setup sees as you toggle each view.',
  },
  {
    id: 'note',
    title: 'Record a field question on the right',
    text: 'Click A0075 in the LEFT observer list. In Practice review on the RIGHT, open the Decision dropdown and choose needs inspection. Enter a question in Notes, then click Save review.',
    target: 'review-fields',
    extra:
      'For example: “Is there an eye-height gap through the foreground branches?” Practice notes stay separate from real reviews. Keep, reject and needs inspection record your judgment; none certify safe or legal access.',
  },
  {
    id: 'export',
    title: 'Choose observers and download below the left list',
    text: 'In the LEFT observer cards, check Export for A0075, V010 and V008. Then click GPX or KML in the export panel BELOW the left-hand list. The two highlighted areas show both controls.',
    target: 'export-panel',
    extra:
      'PRACTICE files contain the saved observer locations, not target openings or routes. Import a real export with your mapping app’s waypoint import feature; verify names and coordinates before field use.',
  },
];
const areaSteps = [
  {
    id: 'draw',
    title: 'Draw a practice area on the map',
    text: 'We’ve opened cached Soap Creek imagery for practice. In the RIGHT panel, choose Draw boundary. Click at least three corners in the clear part of the MAP, finish the shape, then choose Use this boundary.',
    target: 'drawing',
    extra:
      'The orange boundary defines where you are considering standing to glass. This is a training shape, not a suggested hunting area. No analysis or source acquisition starts; online imagery is optional.',
  },
  {
    id: 'edit',
    title: 'Check and adjust your boundary',
    text: 'Inspect the orange shape on the MAP. Use Edit vertices in the RIGHT panel to drag a corner if needed, then choose Use this boundary again. Undo, Cancel drawing and Clear boundary let you correct mistakes.',
    target: 'drawing',
    extra:
      'Your shape is preserved exactly as drawn; invalid shapes must be corrected. For a real area you can draw the same way or use Import file. Drawing uses 2D so corners land accurately.',
  },
  {
    id: 'settings',
    title: 'Understand the settings on the right',
    text: 'Look at the settings in the RIGHT panel. Open How locations are chosen, then Advanced scoring settings. Hover over, focus or click each question mark for a plain-language explanation. The current defaults are a starting point, not a guarantee of suitable setups.',
    target: 'run-settings',
    extra:
      'View radius controls analysis distance. Locations to evaluate controls initial sampling, not shortlist size; too many separated points for a small area causes a failure. Assumed inspection time affects scores, not visible terrain or a stop duration. Maximum download size limits analysis acquisition; online browsing is separate.',
  },
  {
    id: 'handoff',
    title: 'What happens for your real area',
    text: 'Practice stops here. After this lesson, choose New baseline run, draw YOUR area or import its boundary, and give it a new name. Prepare the acquisition plan and review source details, estimated size and the cap before explicitly allowing downloads.',
    target: 'run-settings',
    extra:
      'Analysis jobs show actual stages, elapsed time and logs. You can cancel a running subprocess and review partial runs. New-area runs use the terrain baseline; Soap Creek vegetation experiments do not generalize automatically.',
  },
];
type TrainingState = {
  notes: Notes;
  lessons: Partial<Record<Lesson, Progress>>;
  current: Lesson | null;
  draft: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
};
function load(): TrainingState {
  try {
    const v = JSON.parse(localStorage.getItem(key) || 'null');
    if (v) return v;
    const old = JSON.parse(localStorage.getItem('huntmaps-training-v1') || '{}');
    const p = old.progress;
    return {
      notes: old.notes || {},
      lessons: p
        ? {
            [p.lesson]: {
              lesson: p.lesson,
              step: p.lesson === 'review' ? 'select' : 'draw',
              paused: true,
              complete: !!p.complete,
            },
          }
        : {},
      current: p?.lesson || null,
      draft: null,
    };
  } catch {
    return { notes: {}, lessons: {}, current: null, draft: null };
  }
}
export function useTraining() {
  const [initial] = useState(load),
    [lessons, setLessons] = useState<Partial<Record<Lesson, Progress>>>(initial.lessons || {}),
    [current, setCurrent] = useState<Lesson | null>(initial.current || null),
    [notes, setNotes] = useState<Notes>(initial.notes || {}),
    [draft, setDraft] = useState<GeoJSON.Polygon | GeoJSON.MultiPolygon | null>(
      initial.draft || null,
    ),
    [open, setOpen] = useState(false),
    [exported, setExported] = useState(false);
  const progress = current ? lessons[current] || null : null,
    active = !!progress && !progress.paused && !progress.complete;
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify({ lessons, current, notes, draft }));
  }, [lessons, current, notes, draft]);
  function setProgress(p: Progress | null) {
    if (!p) {
      setCurrent(null);
      return;
    }
    setCurrent(p.lesson);
    setLessons((a) => ({ ...a, [p.lesson]: p }));
  }
  return {
    progress,
    setProgress,
    lessons,
    notes,
    draft,
    setDraft,
    open,
    setOpen,
    active,
    exported,
    setExported,
    saveNote: (run: string, id: string, value: { status: string; notes: string }) =>
      setNotes((n) => ({ ...n, [run]: { ...n[run], [id]: value } })),
  };
}
export type Training = ReturnType<typeof useTraining>;
const meanings = {
  layers:
    'Colored cells show where the saved terrain calculation permits a sightline. Trees and branches can still block it. Dashed inspection sectors include hidden ground; they are footprints to inspect, not extra visible acreage. Hide dated imagery to inspect local hillshade.',
  scores:
    'Raw terrain-visible area measures target ground terrain permits you to inspect. Inspection indexes combine saved assumptions; they are not deer probabilities. Soap Creek vegetation screens are experiments specific to that review, not a validated model for other areas.',
  review:
    'Keep means worth further consideration; reject means set aside; needs inspection means an unresolved field question. These decisions do not establish safe or legal access. Practice notes stay separate in this browser.',
  area: 'The observer boundary defines where you could stand to glass, not a target opening or route. Draw it on the map or import a polygon. Manual points are optional. Imported multiple polygons require explicit selection.',
};
export function Meaning({ topic }: { topic: keyof typeof meanings }) {
  return (
    <details className="meaning">
      <summary>What does this mean?</summary>
      <p>{meanings[topic]}</p>
    </details>
  );
}
function VisibilityIllustrations() {
  return (
    <div className="visibility-explainer">
      <figure>
        <figcaption>
          <b>Side view: a ridge blocks ground behind it</b>
        </figcaption>
        <svg
          viewBox="0 0 560 185"
          role="img"
          aria-label="Observer sees the near hillside; the ridge blocks lower ground behind it"
        >
          <path
            d="M35 140 L170 140 L300 55 L355 140 L535 140 L535 175 L35 175Z"
            fill="#e2e9d5"
            stroke="#5b7351"
            strokeWidth="2"
          />
          <path d="M170 140 L300 55" fill="none" stroke="#00a6bd" strokeWidth="7" />
          <path
            d="M35 125 L300 55 L535 -7"
            fill="none"
            stroke="#28483e"
            strokeDasharray="6 4"
            strokeWidth="2"
          />
          <path d="M300 55 L355 140 L535 140" fill="none" stroke="#8f8d86" strokeWidth="7" />
          <circle cx="35" cy="125" r="7" fill="#24483c" />
          <text x="8" y="110">
            Observer
          </text>
          <text x="155" y="65">
            Visible hillside
          </text>
          <text x="250" y="20">
            Ridge blocks view
          </text>
          <text x="370" y="122">
            Hidden ground
          </text>
        </svg>
        <p>
          Dashed line: sightline to the ridge. The lower ground behind it is hidden by terrain.
          Trees are not modeled in this illustration.
        </p>
      </figure>
      <figure>
        <figcaption>
          <b>Map view: colored cells belong to this observer</b>
        </figcaption>
        <svg
          viewBox="0 0 560 185"
          role="img"
          aria-label="Map view with observer dot, blue terrain-visible cells, and a larger dashed inspection sector"
        >
          <path
            d="M50 140 L480 20 L480 160 Z"
            fill="#f5e9cb"
            stroke="#a78a4d"
            strokeDasharray="7 5"
            strokeWidth="2"
          />
          <path
            d="M105 123 L185 65 L250 65 L250 95 L280 95 L280 135 L210 135 L210 155 L140 155 Z M340 45 L375 45 L375 85 L340 85Z"
            fill="#00a6bd"
            opacity=".7"
          />
          <circle cx="50" cy="140" r="8" fill="#24483c" />
          <text x="12" y="173">
            Observer
          </text>
          <text x="120" y="43">
            Terrain-visible cells
          </text>
          <text x="300" y="116">
            Hidden ground (example)
          </text>
          <text x="295" y="175">
            Dashed: inspection footprint
          </text>
        </svg>
        <p>
          Dashed inspection footprints can contain visible and hidden ground; they do not outline
          all visible cells. On actual maps, uncolored ground may also be outside the evaluated
          target area. These are schematic examples, not saved results.
        </p>
      </figure>
    </div>
  );
}
export function Learning({
  exampleAvailable,
  training: t,
  selected,
  compare,
  hiddenViews,
  exportIds,
  status,
  note,
  saved,
  geometry,
  onStart,
  onExit,
}: {
  exampleAvailable: boolean;
  training: Training;
  selected: string;
  compare: string[];
  hiddenViews: string[];
  exportIds: string[];
  status: string;
  note: string;
  saved: string;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
  onStart: (l: Lesson) => boolean;
  onExit: () => void;
}) {
  const [toggled, setToggled] = useState(false),
    [restored, setRestored] = useState(false),
    dialog = useRef<HTMLDialogElement>(null);
  const p = t.progress,
    lesson = p?.lesson || 'review',
    steps = lesson === 'review' ? reviewSteps : areaSteps,
    step = Math.max(
      0,
      steps.findIndex((s) => s.id === p?.step),
    ),
    current = steps[step];
  useEffect(() => {
    if (t.open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [t.open]);
  useEffect(() => {
    if (t.active && p?.step === 'separate' && hiddenViews.includes('V010')) setToggled(true);
    if (toggled && !hiddenViews.includes('V010')) setRestored(true);
  }, [hiddenViews, t.active, p?.step, toggled]);
  useEffect(() => {
    if (!t.active || t.open) return;
    const timer = setTimeout(() => {
      document
        .querySelectorAll('.tour-highlight')
        .forEach((e) => e.classList.remove('tour-highlight'));
      const target = document.querySelector(`[data-tour="${current.target}"]`);
      if (target) {
        target.classList.add('tour-highlight');
        target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        if (current.id === 'note')
          target.querySelector<HTMLSelectElement>('select')?.focus({ preventScroll: true });
      }
      if (current.id === 'export')
        document.querySelector('[data-tour="observer-list"]')?.classList.add('tour-highlight');
    }, 250);
    return () => {
      clearTimeout(timer);
      document
        .querySelectorAll('.tour-highlight')
        .forEach((e) => e.classList.remove('tour-highlight'));
    };
  }, [t.active, t.open, p?.step, selected, saved, geometry]);
  function start(l: Lesson, resume = false) {
    if (!onStart(l)) return;
    setToggled(false);
    setRestored(false);
    t.setExported(false);
    t.setProgress({
      lesson: l,
      step: resume
        ? t.lessons[l]?.step || (l === 'review' ? 'select' : 'draw')
        : l === 'review'
          ? 'select'
          : 'draw',
      paused: false,
      complete: false,
    });
    t.setOpen(false);
  }
  const trio = ['A0075', 'V010', 'V008'],
    ready =
      lesson === 'area'
        ? !!geometry
        : [
            selected === 'A0075',
            compare.length === 3 && trio.every((i) => compare.includes(i)),
            toggled && restored,
            selected === 'A0075' &&
              status === 'needs inspection' &&
              !!note.trim() &&
              saved === 'Practice review saved separately',
            trio.every((i) => exportIds.includes(i)) && t.exported,
          ][step];
  function next() {
    if (!p) return;
    if (step === steps.length - 1) {
      t.setProgress({ ...p, complete: true });
      onExit();
      t.setOpen(true);
    } else t.setProgress({ ...p, step: steps[step + 1].id });
  }
  return (
    <>
      {!p && (
        <div className="learn-welcome">
          New to HuntMaps2?{' '}
          <button onClick={() => t.setOpen(true)}>Start with the saved example</button>
          <span>No prior run needed · no analysis or source acquisition</span>
        </div>
      )}
      {p?.paused && !p.complete && (
        <div className="learn-welcome">
          Your lesson is paused.{' '}
          <button disabled={!exampleAvailable} onClick={() => start(p.lesson, true)}>
            Resume lesson
          </button>
          <button onClick={() => t.setOpen(true)}>Learning path</button>
        </div>
      )}
      {t.active && (
        <section className="training-coach" aria-label="Practice lesson">
          <div>
            <b>
              Practice · Lesson {lesson === 'review' ? 1 : 2} · Step {step + 1} of {steps.length}
            </b>
            <p className="hint">
              Notes and drawn areas stay separate from real reviews and run inputs. No analysis or
              source acquisition during practice; online imagery is optional.
            </p>
          </div>
          <div aria-live="polite">
            <h2>{current.title}</h2>
            <p>{current.text}</p>
            <details className="step-explanation" open>
              <summary>Why this matters</summary>
              <p>{current.extra}</p>
            </details>
            <div className="row">
              <button
                disabled={step === 0}
                onClick={() => p && t.setProgress({ ...p, step: steps[step - 1].id })}
              >
                Back
              </button>
              <button className="primary" disabled={!ready} onClick={next}>
                {step === steps.length - 1 ? 'Finish lesson' : 'Next step'}
              </button>
              <button
                onClick={() => {
                  if (p) t.setProgress({ ...p, paused: true });
                  onExit();
                }}
              >
                Pause / exit practice
              </button>
              <button onClick={() => t.setOpen(true)}>Open guide</button>
            </div>
            {!ready && (
              <small>Complete the highlighted action to continue, or pause anytime.</small>
            )}
          </div>
        </section>
      )}
      <dialog
        ref={dialog}
        className="learning-dialog"
        onCancel={() => t.setOpen(false)}
        onClose={() => t.setOpen(false)}
        aria-labelledby="learn-title"
      >
        <div className="section-title">
          <h2 id="learn-title">Learn HuntMaps2</h2>
          <button autoFocus onClick={() => t.setOpen(false)} aria-label="Close learning center">
            Close
          </button>
        </div>
        <p>
          Follow these two lessons in order. Start with completed results, then practice drawing an
          area. You do not need to generate a run first.
        </p>
        {p?.complete && (
          <p className="notice" role="status">
            Lesson complete. Your practice work stays separate.
          </p>
        )}
        <div className="lesson-cards learning-path">
          {(['review', 'area'] as Lesson[]).map((l, i) => (
            <article className={i === 0 ? 'recommended' : ''} key={l}>
              <span className="path-number">{i + 1}</span>
              <div>
                <small>
                  {t.lessons[l]?.complete
                    ? '✓ Completed'
                    : i === 0
                      ? 'START HERE · recommended first'
                      : 'NEXT · after reviewing the example'}
                </small>
                <h3>{i === 0 ? 'Review the saved example' : 'Draw your own area'}</h3>
                <p>
                  {i === 0
                    ? 'Select A0075, compare three alternatives, record a practice question and export observers.'
                    : 'Learn drawing and editing over cached imagery, then understand settings for your real area.'}
                </p>
                <button
                  className={i === 0 ? 'primary' : ''}
                  disabled={!exampleAvailable}
                  onClick={() => start(l)}
                >
                  {i === 0 ? 'Start lesson 1' : 'Start lesson 2'}
                </button>
                {t.lessons[l] && !t.lessons[l]?.complete && (
                  <button disabled={!exampleAvailable} onClick={() => start(l, true)}>
                    Resume lesson {i + 1}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
        {!exampleAvailable && (
          <p className="notice">
            The lessons need the local Soap Creek decision review. If it is unavailable after
            results load, use the guide with your own saved run.
          </p>
        )}
        <h3>Quick reference</h3>
        <details>
          <summary>Understand the visible-ground overlay</summary>
          <p>{meanings.layers}</p>
          <VisibilityIllustrations />
        </details>
        <details>
          <summary>Where the controls are</summary>
          <p>
            LEFT: observer cards; expand saved alternatives to see related setups. Their Compare and
            Export checkboxes; GPX/KML below the list. TOP OF MAP: individual view toggles. RIGHT:
            coordinates, metrics, review decisions and notes. New baseline run opens drawing,
            imports and settings on the right.
          </p>
          <p>Comparison and export explanations appear as you work through lesson 1.</p>
        </details>
        <details>
          <summary>Terrain, imagery and uncertainty</summary>
          <p>{meanings.scores}</p>
          <p>
            3D displays saved bare-earth terrain at true scale, not trees or an eye-level sightline
            simulation. Check imagery dates below the map. Cached maps and help work offline; new
            acquisition may need a network.
          </p>
        </details>
        <p className="hint">
          Practice progress, notes and the practice drawing stay in this browser profile. Clearing
          browser storage removes them. Real reviews remain on disk.
        </p>
        <button
          onClick={() => {
            if (t.active && p) {
              t.setProgress({ ...p, paused: true });
              onExit();
            }
            t.setOpen(false);
          }}
        >
          Skip training and use the tool
        </button>
      </dialog>
    </>
  );
}

export function practiceExport(
  fmt: string,
  points: { id: string; longitude: number; latitude: number; parent: string }[],
  notes: Record<string, { notes: string }>,
) {
  const doc = document.implementation.createDocument(
      fmt === 'gpx' ? 'http://www.topografix.com/GPX/1/1' : 'http://www.opengis.net/kml/2.2',
      fmt === 'gpx' ? 'gpx' : 'kml',
    ),
    root = doc.documentElement;
  if (fmt === 'gpx') {
    root.setAttribute('version', '1.1');
    root.setAttribute('creator', 'HuntMaps2 practice lesson');
  }
  const add = (parent: Element, name: string, value?: string) => {
      const e = doc.createElementNS(root.namespaceURI, name);
      if (value !== undefined) e.textContent = value;
      parent.appendChild(e);
      return e;
    },
    container = fmt === 'kml' ? add(root, 'Document') : root;
  points.forEach((p) => {
    const w = add(container, fmt === 'gpx' ? 'wpt' : 'Placemark'),
      name = `PRACTICE ${p.id}${p.parent ? ' (alternative to ' + p.parent + ')' : ''}`,
      desc = 'Training example; provisional observer, not a route. ' + (notes[p.id]?.notes || '');
    if (fmt === 'gpx') {
      w.setAttribute('lat', String(p.latitude));
      w.setAttribute('lon', String(p.longitude));
      add(w, 'name', name);
      add(w, 'desc', desc);
    } else {
      add(w, 'name', name);
      add(w, 'description', desc);
      add(add(w, 'Point'), 'coordinates', `${p.longitude},${p.latitude},0`);
    }
  });
  const url = URL.createObjectURL(
      new Blob([new XMLSerializer().serializeToString(doc)], { type: 'application/xml' }),
    ),
    a = document.createElement('a');
  a.href = url;
  a.download = `PRACTICE-soap-creek-observers.${fmt}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
