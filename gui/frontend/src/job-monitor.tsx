import JobProgress from './job-progress';
import JobLogs from './job-logs';
import type { Job } from './types';
export default function JobMonitor({
  jobs,
  running,
  trainingActive,
  onAction,
  onOpen,
}: {
  jobs: Job[];
  running: boolean;
  trainingActive: boolean;
  onAction: (job: Job, action: 'cancel' | 'resume') => void;
  onOpen: (name: string) => void;
}) {
  return jobs.length > 0 ? (
    <details className="jobs" open={running}>
      <summary>
        Analysis jobs {running ? '· active' : ''} · {jobs.length}
      </summary>
      {jobs.slice(0, 6).map((j) => (
        <div className="job" key={j.id}>
          <div className="row">
            <b>
              {j.name || 'Job'} · {j.kind}
            </b>
            <span className={'status ' + j.status}>{j.status}</span>
            <span>{j.elapsed_s.toFixed(1)} s</span>
            {['running', 'cancelling'].includes(j.status) ? (
              <button disabled={j.status === 'cancelling'} onClick={() => onAction(j, 'cancel')}>
                Cancel job
              </button>
            ) : (
              <>
                {!j.kind.startsWith('first-person') && j.kind !== 'waypoint-update' && (
                  <button disabled={trainingActive} onClick={() => onAction(j, 'resume')}>
                    {j.recovery_action === 'adjust'
                      ? 'Review sampling settings'
                      : j.recovery_action === 'review'
                        ? 'Review source plan'
                        : 'Review / resume plan'}
                  </button>
                )}
                {j.kind === 'waypoint-update' && (
                  <small>
                    Retry from Update waypoint; previous committed location is retained on failure.
                  </small>
                )}
                {j.kind.startsWith('first-person') && (
                  <small>Review source preparation in View from this setup.</small>
                )}
                {j.status === 'complete' && j.kind === 'baseline' && (
                  <button
                    disabled={trainingActive}
                    onClick={() => {
                      onOpen(j.name);
                    }}
                  >
                    Open results
                  </button>
                )}
              </>
            )}
          </div>
          <p>{j.stage}</p>
          <JobProgress job={j} />
          {j.engine_event && (
            <p className="hint">
              Latest engine record: {j.engine_event.stage || j.engine_event.command || 'see log'}{' '}
              {j.engine_event.wall_s !== undefined ? `· ${j.engine_event.wall_s}s` : ''}
            </p>
          )}
          {j.error && <p className="error">{j.error}</p>}
          {j.failed_stage && <small>Failed during: {j.failed_stage}</small>}
          <JobLogs id={j.id} label="Actual subprocess log" />
        </div>
      ))}
    </details>
  ) : null;
}
