import type { Candidate, Review } from './types';
const num = (value: unknown) => (typeof value === 'number' ? value.toFixed(3) : 'Not saved');
export default function CandidateCard({
  p,
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
        onClick={() => chooseOriginal(p.id)}
      >
        <strong>
          {p.id}
          {p.working_revision ? ' · updated' : ''}
        </strong>
        <span>{p.parent ? 'Alternative to ' + p.parent : p.neighborhood || 'Original setup'}</span>
        {matching !== undefined && <b>{num(matching)} km² matching visible terrain</b>}
        <small>
          {num(p.metrics.raw_km2)} km² original terrain view{' '}
          {p.working_revision ? '· working location ' : ''}
          {annotations[p.id]?.status && annotations[p.id].status !== 'unmarked'
            ? '· ' + annotations[p.id].status
            : ''}
        </small>
      </button>
      {typeof p.metrics.foreground_category === 'string' && (
        <small className="hint">
          {p.metrics.foreground_category} ·{' '}
          {typeof p.metrics.foreground_tree_mean === 'number'
            ? `${(p.metrics.foreground_tree_mean * 100).toFixed(0)}% tree cover nearby`
            : 'tree cover unknown'}
        </small>
      )}
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
