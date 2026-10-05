import { Icon } from './workspace-ui';
import { area } from './units';
import type { Candidate, Review } from './types';
const num = (value: unknown) => (typeof value === 'number' ? value.toFixed(3) : 'Not saved');
export default function CandidateCard({
  p,
  rank,
  bestArea,
  approach,
  confirmed,
  shortlisted,
  dismissed,
  busy,
  onDecision,
  matching,
  selected,
  activeManual,
  compare,
  annotations,
  exportIds,
  chooseOriginal,
  toggleCompare,
  toggleExport,
}: {
  p: Candidate;
  rank: number;
  bestArea: number;
  approach: boolean;
  confirmed: boolean;
  shortlisted?: boolean;
  dismissed?: boolean;
  busy?: boolean;
  onDecision?: (action: string) => void;
  matching?: number;
  selected: string;
  activeManual: boolean;
  compare: string[];
  annotations: Record<string, Review>;
  exportIds: string[];
  chooseOriginal: (id: string) => void;
  toggleCompare: (id: string) => void;
  toggleExport: (id: string) => void;
}) {
  return (
    <div
      className={'candidate ' + (!activeManual && p.id === selected ? 'active' : '')}
      key={p.id}
      data-tour={'setup-' + p.id}
    >
      <button
        className="candidate-select"
        aria-label={`Select ${p.id}`}
        aria-pressed={!activeManual && p.id === selected}
        onClick={() => chooseOriginal(p.id)}
      >
        <span className="candidate-topline">
          <span className="candidate-rank">{rank > 0 ? String(rank).padStart(2, '0') : '—'}</span>
          <strong>
            {p.id}
            {p.working_revision ? ' · updated' : ''}
          </strong>
          {shortlisted && <Icon name={confirmed ? 'check' : 'save'} size={14} />}
        </span>
        {(p.name || p.parent || p.neighborhood) && (
          <span className="candidate-context">
            {p.name || (p.parent ? 'Near ' + p.parent : p.neighborhood)}
          </span>
        )}
        <span className="candidate-area">
          <b>{area(matching ?? p.metrics.raw_km2)}</b>
          <small>{matching !== undefined ? 'matching view' : 'visible terrain'}</small>
        </span>
        <span
          className="coverage-meter"
          title="Visible area relative to the largest view in this list"
        >
          <i
            style={{
              width: `${bestArea > 0 ? Math.min(100, ((Number(matching ?? p.metrics.raw_km2) || 0) / bestArea) * 100) : 0}%`,
            }}
          />
        </span>
        <span className="candidate-signals">
          <small>{approach ? '✓ Approach selected' : 'Access to review'}</small>
          <small>
            {typeof p.metrics.foreground_tree_mean === 'number'
              ? `${(p.metrics.foreground_tree_mean * 100).toFixed(0)}% nearby trees`
              : 'Cover to inspect'}
          </small>
        </span>
        {matching !== undefined && <small>{area(p.metrics.raw_km2)} total terrain view</small>}
        {annotations[p.id]?.status && annotations[p.id].status !== 'unmarked' && (
          <small>Review: {annotations[p.id].status}</small>
        )}
      </button>
      {onDecision && (
        <div className="candidate-actions">
          <button disabled={busy || shortlisted} onClick={() => onDecision('shortlist')}>
            {shortlisted ? 'Shortlisted' : 'Shortlist'}
          </button>
          <button disabled={busy} onClick={() => onDecision(dismissed ? 'restore' : 'dismiss')}>
            {dismissed ? 'Restore' : 'Dismiss'}
          </button>
        </div>
      )}
      <div className="candidate-actions">
        <label>
          <input
            type="checkbox"
            aria-label={`Compare ${p.id}`}
            checked={compare.includes(p.id)}
            onChange={() => toggleCompare(p.id)}
          />
          Compare
        </label>
        <label>
          <input
            type="checkbox"
            aria-label={`Export ${p.id}`}
            checked={exportIds.includes(p.id)}
            onChange={() => toggleExport(p.id)}
          />
          Export
        </label>
      </div>
    </div>
  );
}
