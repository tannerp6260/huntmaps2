import type { Job } from './types';
import { duration } from './download-review';
export default function JobProgress({ job }: { job: Job | undefined | null }) {
  if (!job) return null;
  const p = job.progress;
  const active = ['running', 'cancelling'].includes(job.status);
  const stale = !!p && active && Date.now() / 1000 - p.updated > 8;
  const fraction =
    p?.total && p.total > 0
      ? Math.min(1, p.completed / p.total)
      : !active
        ? job.status === 'complete'
          ? 1
          : 0
        : undefined;
  return (
    <div className="job-progress" role="status">
      <strong>{p?.label || job.stage}</strong>
      <progress
        aria-label={p?.phase === 'download' ? 'Download progress' : 'Task progress'}
        max={1}
        value={fraction}
      />
      {p?.phase === 'download' ? (
        <small>
          {job.elapsed_s?.toFixed(0) || 0} sec elapsed · {(p.completed / 1e6).toFixed(1)} MB
          transferred
          {p.total != null
            ? ` / ${(p.total / 1e6).toFixed(1)} MB estimated`
            : ' · total uncertain'}{' '}
          ·{' '}
          {active
            ? stale
              ? 'Waiting for data…'
              : p.bytes_per_s
                ? `${(p.bytes_per_s / 1e6).toFixed(1)} MB/s${p.remaining_s != null ? ` · about ${duration(p.remaining_s)} remaining` : ''}`
                : 'Estimating…'
            : job.status}
        </small>
      ) : (
        <small>
          {p?.total != null ? `${p.completed} / ${p.total} items · ` : ''}
          {job.elapsed_s?.toFixed(0) || 0} sec elapsed · {job.status}
        </small>
      )}
      {fraction === 1 && active && <small>This stage is finished; the job is still running.</small>}
    </div>
  );
}
