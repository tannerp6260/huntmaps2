import type { Candidate, Review } from './types';
const num = (value: unknown) => (typeof value === 'number' ? value.toFixed(3) : 'Not saved');
export default function CandidateCard({
  p,
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
        <small>
          {num(p.metrics.raw_km2)} km² original terrain view{' '}
          {p.working_revision ? '· working location ' : ''}
          {annotations[p.id]?.status && annotations[p.id].status !== 'unmarked'
            ? '· ' + annotations[p.id].status
            : ''}
        </small>
        {matching !== undefined && <small>{num(matching)} km² matching visible terrain</small>}
      </button>
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
