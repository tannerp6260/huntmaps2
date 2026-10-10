import { Component, useState } from 'react';
import type { Candidate } from './types';
import type { Workflow } from './workflow';
import { area } from './units';

export type Stage = 'find' | 'approach' | 'inspect' | 'save';
export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    mountain: (
      <>
        <path d="m2 19 7-13 5 8 3-5 5 10H2Z" />
        <path d="m6 12 3 2 2-3" />
      </>
    ),
    find: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 6 6" />
      </>
    ),
    approach: (
      <>
        <circle cx="5" cy="19" r="2" />
        <circle cx="19" cy="5" r="2" />
        <path d="M5 17v-5a3 3 0 0 1 3-3h8a3 3 0 0 0 3-3" />
      </>
    ),
    inspect: (
      <>
        <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    save: <path d="M6 3h12v18l-6-4-6 4V3Z" />,
    layers: (
      <>
        <path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5" />
      </>
    ),
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    check: <path d="m5 12 4 4L19 6" />,
    pin: (
      <>
        <path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" />
        <circle cx="12" cy="10" r="2" />
      </>
    ),
    tune: (
      <>
        <path d="M3 7h18M3 17h18" />
        <path d="M8 4v6M16 14v6" />
      </>
    ),
    close: <path d="m6 6 12 12M6 18 18 6" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.pin}
    </svg>
  );
}
export function WorkflowNavigation({
  stage,
  shortlisted,
  approached,
  confirmed,
  reviewReady,
  disabled,
  onStage,
}: {
  stage: Stage;
  shortlisted: number;
  approached: number;
  confirmed: number;
  reviewReady: boolean;
  disabled: boolean;
  onStage: (stage: Stage) => void;
}) {
  const stages: {
    id: Stage;
    label: string;
    detail: string;
    complete: boolean;
    unavailable: boolean;
    reason: string;
  }[] = [
    {
      id: 'find',
      label: 'Find',
      detail: shortlisted ? `${shortlisted} shortlisted` : 'Discover glassing setups',
      complete: shortlisted > 0,
      unavailable: false,
      reason: '',
    },
    {
      id: 'approach',
      label: 'Approach',
      detail: `${approached} selected`,
      complete: approached > 0 && reviewReady,
      unavailable: !shortlisted || disabled,
      reason: 'Shortlist a setup in Find to compare approaches.',
    },
    {
      id: 'inspect',
      label: 'Inspect',
      detail: 'See the terrain',
      complete: confirmed > 0,
      unavailable: !approached || !reviewReady || disabled,
      reason: 'Select an approach or dismiss each remaining spot before inspecting.',
    },
    {
      id: 'save',
      label: 'Save',
      detail: `${confirmed} confirmed`,
      complete: confirmed > 0,
      unavailable: disabled,
      reason: 'Collections are separate from practice.',
    },
  ];
  return (
    <nav className="workflow-stages" aria-label="Scouting workflow">
      {stages.map((s, index) => (
        <button
          key={s.id}
          aria-current={stage === s.id ? 'step' : undefined}
          disabled={s.unavailable}
          title={s.unavailable ? s.reason : `${s.label} · ${s.detail}`}
          onClick={() => onStage(s.id)}
        >
          <span className={'stage-number ' + (s.complete ? 'complete' : '')}>
            {s.complete && stage !== s.id ? <Icon name="check" size={14} /> : `0${index + 1}`}
          </span>
          <span className="stage-copy">
            <b>{s.label}</b>
            <small>{s.detail}</small>
          </span>
          <Icon name={s.id} />
        </button>
      ))}
    </nav>
  );
}
export function EmptyState({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="empty-state">
      <Icon name="mountain" size={36} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function SelectedSetup({
  candidate,
  id,
  name,
  matching,
  workflow,
  busy,
  onDetails,
  onInspect,
  onDecision,
  onApproach,
}: {
  candidate: Pick<Candidate, 'metrics'> | null;
  id: string;
  name?: string;
  matching?: number;
  workflow: Workflow | null;
  busy: boolean;
  onApproach: () => void;
  onDetails: () => void;
  onInspect: () => void;
  onDecision: (action: string) => void;
}) {
  const point = workflow?.points[id];
  if (!id) return null;
  return (
    <section className="selected-setup" aria-label="Selected setup">
      <div className="selected-identity">
        <span className="selection-pin">
          <Icon name="pin" />
        </span>
        <div>
          <span className="eyebrow">Selected setup</span>
          <b>{name || id}</b>
        </div>
      </div>
      <div className="selection-metric">
        <strong>{area(matching ?? candidate?.metrics.raw_km2)}</strong>
        <small>{matching !== undefined ? 'matching terrain' : 'visible terrain'}</small>
      </div>
      <div className="selection-evidence">
        <b>
          {point?.confirmed
            ? '✓ Saved to collection'
            : point?.approach
              ? 'Approach selected'
              : 'Access to review'}
        </b>
        <small>
          {point?.confirmed
            ? 'Provisional · field checks remain'
            : point?.approach
              ? 'Ready for terrain inspection'
              : 'Permissions & conditions unverified'}
        </small>
      </div>
      <div className="selection-actions">
        <button onClick={onDetails}>Setup details</button>
        <button onClick={onInspect} title="Open the modeled view from this setup">
          <Icon name="inspect" /> View
        </button>
        {point?.shortlisted && !point?.approach && (
          <button className="primary" onClick={onApproach}>
            Plan approach <Icon name="arrow" size={14} />
          </button>
        )}
        <button
          className={point?.shortlisted ? 'shortlisted-state' : 'primary'}
          disabled={busy || point?.shortlisted}
          onClick={() => onDecision('shortlist')}
        >
          <Icon name={point?.shortlisted ? 'check' : 'save'} />
          {point?.shortlisted ? 'Shortlisted' : 'Shortlist'}
        </button>
      </div>
    </section>
  );
}
export function SavedCollection({
  workflow,
  runId,
  candidates,
  selected,
  busy,
  onSelect,
  onStage,
  onRemove,
}: {
  workflow: Workflow | null;
  runId: string;
  candidates: (Pick<Candidate, 'id' | 'name'> & { metrics?: Candidate['metrics'] })[];
  selected: string;
  busy: boolean;
  onSelect: (id: string) => void;
  onStage: (stage: Stage) => void;
  onRemove: (id: string) => void;
}) {
  const [tab, setTab] = useState<'confirmed' | 'shortlist'>('confirmed');
  const retained = Object.values(workflow?.points || {}).filter((p) => p.shortlisted);
  const confirmed = retained.filter((p) => p.confirmed && !p.stale);
  const list = tab === 'confirmed' ? confirmed : retained;
  return (
    <aside className="saved-collection">
      <div className="panel-heading">
        <span className="eyebrow">Your scouting collection</span>
        <h2>Worth coming back to.</h2>
        <p>Keep your best setups, with the evidence behind each decision.</p>
      </div>
      <div className="collection-tabs" role="group" aria-label="Collection filter">
        <button aria-pressed={tab === 'confirmed'} onClick={() => setTab('confirmed')}>
          Confirmed <b>{confirmed.length}</b>
        </button>
        <button aria-pressed={tab === 'shortlist'} onClick={() => setTab('shortlist')}>
          Shortlist <b>{retained.length}</b>
        </button>
      </div>
      <div className="collection-list">
        {!list.length ? (
          <EmptyState
            title={tab === 'confirmed' ? 'Build your collection' : 'Start with a promising setup'}
          >
            {tab === 'confirmed'
              ? 'Shortlist a setup, choose an approach, then inspect its view before confirming.'
              : 'Explore the ranked setups in Find and shortlist the ones you want to investigate.'}
            <button
              className="primary wide"
              onClick={() => onStage(retained.length ? 'approach' : 'find')}
            >
              {retained.length ? 'Review approaches' : 'Find setups'} <Icon name="arrow" />
            </button>
          </EmptyState>
        ) : (
          list.map((p) => {
            const c = candidates.find((c) => c.id === p.point.id);
            return (
              <article
                key={p.point.id}
                className={'collection-item ' + (selected === p.point.id ? 'active' : '')}
              >
                <button
                  className="collection-select"
                  aria-pressed={selected === p.point.id}
                  onClick={() => onSelect(p.point.id)}
                >
                  <Icon name="save" />
                  <strong>{c?.name || p.point.id}</strong>
                  <span className="status-badge">
                    {p.stale ? 'Needs review' : p.confirmed ? 'Confirmed' : 'Shortlisted'}
                  </span>
                </button>
                <p>{area(c?.metrics?.raw_km2)} visible terrain</p>
                <div className="evidence-steps">
                  <span>✓ Shortlisted</span>
                  <span>{p.approach ? '✓' : '○'} Approach</span>
                  <span>{p.viewed ? '✓' : '○'} Inspected</span>
                </div>
                <div className="row">
                  <a
                    className="button"
                    href={`/api/runs/${runId}/export/gpx?ids=${encodeURIComponent(p.point.id)}`}
                  >
                    Waypoint GPX
                  </a>
                  {p.approach && (
                    <a
                      href={`/api/approaches/${p.approach.scenario}/export/gpx?waypoint=${encodeURIComponent(p.point.id)}&alternative=${p.approach.alternative}`}
                    >
                      Approach GPX
                    </a>
                  )}
                  <button
                    className="quiet"
                    disabled={busy}
                    onClick={() => onRemove(p.point.id)}
                    aria-label={`Remove ${p.point.id} from collection`}
                  >
                    Remove
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>
      {!!confirmed.length && (
        <div className="collection-export">
          <b>Export confirmed setups</b>
          <div className="row">
            {['gpx', 'kml'].map((type) => (
              <a
                className="button"
                key={type}
                href={`/api/runs/${runId}/export/${type}?ids=${confirmed.map((p) => encodeURIComponent(p.point.id)).join(',')}`}
              >
                {type.toUpperCase()} · {confirmed.length} setups
              </a>
            ))}
          </div>
        </div>
      )}
      <p className="collection-note">
        Provisional desktop scouting. Confirmed means reviewed by you; permissions, footing and
        field sightlines still need checking.
      </p>
    </aside>
  );
}

// A failed lazy scene module must never take the scouting map down with it.
export class SceneBoundary extends Component<
  { children: React.ReactNode; onClose: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="fp-backdrop">
        <section
          className="management-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="View could not open"
        >
          <h2>View could not open</h2>
          <p>
            The terrain viewer could not load. Your scouting workspace is still available. Reload
            the application to try again.
          </p>
          <div className="row">
            <button className="primary" onClick={() => location.reload()}>
              Reload application
            </button>
            <button autoFocus onClick={this.props.onClose}>
              Return to map
            </button>
          </div>
        </section>
      </div>
    );
  }
}
