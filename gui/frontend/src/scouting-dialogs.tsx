import { useEffect, useRef, type ReactNode } from 'react';
import JobProgress from './job-progress';
import type { Job } from './types';

export function ScoutingDialog({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose?: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !ref.current?.open) ref.current?.showModal();
    else if (!open) ref.current?.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="scouting-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose?.();
      }}
    >
      <div className="section-title">
        <h2>{title}</h2>
        {onClose && (
          <button aria-label={`Close ${title}`} onClick={onClose}>
            Close
          </button>
        )}
      </div>
      {children}
    </dialog>
  );
}

export function StartupChooser({
  open,
  loaded,
  hasWork,
  onChoose,
}: {
  open: boolean;
  loaded: boolean;
  hasWork: boolean;
  onChoose: (choice: 'new' | 'training' | 'existing') => void;
}) {
  return (
    <ScoutingDialog open={open} title="Welcome to HuntMaps2">
      <p>Where would you like to start?</p>
      <div className="startup-choices">
        <button className="primary" onClick={() => onChoose('new')}>
          New scouting area
        </button>
        <p>Draw or import your own observer area and find places to glass.</p>
        <button onClick={() => onChoose('training')}>Training</button>
        <p>Learn with the saved example, or resume a lesson.</p>
        <button disabled={!loaded || !hasWork} onClick={() => onChoose('existing')}>
          Open existing work
        </button>
        <p>
          {loaded && !hasWork
            ? 'No saved areas or generation jobs are available.'
            : 'Return to saved areas or job recovery.'}
        </p>
      </div>
    </ScoutingDialog>
  );
}

export function AboutFind({
  open,
  onClose,
  minutes,
}: {
  open: boolean;
  onClose: () => void;
  minutes: number;
}) {
  return (
    <ScoutingDialog open={open} title="About Find" onClose={onClose}>
      <h3>How locations are found</h3>
      <p>
        Your observer boundary defines where you could stand to glass. Target terrain extends up to
        the view radius beyond those positions. Roads, trails and nearby vegetation restrictions
        change observer eligibility; they do not remove targets or obstruction terrain.
      </p>
      <p>
        The engine samples sections of your area, general background locations, and terrain
        resembling benches, shoulders and ridge breaks. A fixed seed makes the same inputs
        repeatable. Broad sampling uses 80% of the evaluation budget; nearby refinement uses up to
        20%. Spacing starts at 164 yards and decreases for small areas, down to the grid resolution.
        Exhausted eligible cells can leave part of the budget unused.
      </p>
      <h3>What the results mean</h3>
      <p>
        Recommendations rank matching terrain-visible area. More evaluations mean more processing,
        without guaranteeing an optimum. All evaluated setups remain available, along with original
        engine rankings. Scores are not deer probabilities, and mapped roads or trails do not
        establish legal or safe access.
      </p>
      <p>
        Nearby vegetation screens where you stand. Coarse tree cover cannot verify individual trees,
        small clearings or foreground branches. Unknown cover remains unknown.
      </p>
      <h3>Calculation assumptions</h3>
      <p>
        The inherited calculation allocates {minutes} minutes to inspecting a view. This affects
        inherited indices, not terrain-visible area, and is not a suggested visit duration.
      </p>
      <h3>Sources and limits</h3>
      <p>
        Generate setups prepares sources, reuses verified local files, and downloads required data
        within your displayed transfer cap. Source estimates, dates and technical details remain
        available in the source plan.
      </p>
      <p>
        Existing limits: 3 million grid cells, 1536 MiB analysis memory, 900 seconds per engine
        batch, and 800 MB outputs. Analysis acquisition does not include imagery or legal-access
        evidence. Online basemap tiles are separate browsing context.
      </p>
    </ScoutingDialog>
  );
}

export function JobFailure({ job }: { job: Job }) {
  if (!job.error) return null;
  const provider = job.failure_code === 'provider_failed';
  const source = job.error
    .match(/([\w .-]+service) returned an error:/)?.[1]
    ?.split(':')
    .pop()
    ?.trim();
  return (
    <>
      <p className="error" role="alert">
        {provider
          ? `${source || 'The source provider'} returned an error instead of usable data. Generation stopped. Verified downloads are retained. Retry to request the missing data again.`
          : job.error}
      </p>
      {provider && (
        <details>
          <summary>Technical diagnostics</summary>
          <p className="hint">
            The original provider response is retained in this run's downloads/rejected folder.
            Retrying is not a confirmed fix for the provider error.
          </p>
          <pre>{job.error}</pre>
        </details>
      )}
    </>
  );
}

export function GenerationDialog({
  open,
  job,
  message,
  active,
  onClose,
  onCancel,
  onRetry,
  onResults,
}: {
  open: boolean;
  job?: Job;
  message: string;
  active: boolean;
  onClose: () => void;
  onCancel: () => void;
  onRetry?: () => void;
  onResults?: () => void;
}) {
  return (
    <ScoutingDialog open={open} title="Generating setups" onClose={onClose}>
      {job ? (
        <JobProgress job={job} />
      ) : (
        <div role="status">
          <p>{message || 'Preparing sources…'}</p>
          {active && <progress aria-label="Preparing sources" />}
        </div>
      )}
      {job?.error && <JobFailure job={job} />}
      {message && job && <p role="status">{message}</p>}
      <div className="generation-actions">
        {active && (
          <button disabled={job?.status === 'cancelling'} onClick={onCancel}>
            Cancel current job
          </button>
        )}
        {active && <button onClick={onClose}>Continue in background</button>}
        {onRetry && <button onClick={onRetry}>Retry</button>}
        {onResults && (
          <button className="primary" onClick={onResults}>
            Open results
          </button>
        )}
      </div>
    </ScoutingDialog>
  );
}
