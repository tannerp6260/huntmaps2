export type DownloadReviewInfo = {
  storage?: {
    reserve_bytes: number;
    required_bytes: number;
    processing_estimate_uncertain: boolean;
    blocked: boolean;
    volumes: { path: string; free_bytes: number }[];
  };
  download_time?: { basis: string; minimum_s: number | null; maximum_s: number | null };
};
export const duration = (seconds: number) =>
  seconds < 60
    ? `${Math.max(1, Math.ceil(seconds))} sec`
    : seconds < 3600
      ? `${Math.ceil(seconds / 60)} min`
      : `${(seconds / 3600).toFixed(1)} hr`;
export default function DownloadReview({
  plan,
  bytes,
}: {
  plan: DownloadReviewInfo;
  bytes: number | null;
}) {
  const estimate = plan.download_time;
  return (
    <div className="download-review">
      <p>
        <strong>Estimated download time: </strong>
        {bytes === 0
          ? 'No download needed'
          : estimate?.minimum_s != null && estimate.maximum_s != null
            ? `${duration(estimate.minimum_s)}–${duration(estimate.maximum_s)} · ${estimate.basis === 'measured' ? 'recent measured provider speed' : estimate.basis === 'mixed' ? 'measured and estimated provider speeds' : estimate.basis}`
            : 'Unavailable until source sizes are known'}
      </p>
      <small>
        Approximate transfer time. We use recent provider measurements when available, otherwise a
        small background speed check or a 20 Mbps default. Processing takes additional time.
      </small>
      {plan.storage && (
        <>
          <p>
            Available storage:{' '}
            {Math.min(...plan.storage.volumes.map((v) => v.free_bytes / 2 ** 30)).toFixed(1)} GiB ·
            keep {Math.round(plan.storage.reserve_bytes / 2 ** 30)} GiB free. Estimated working
            space: {(plan.storage.required_bytes / 2 ** 30).toFixed(1)} GiB.
          </p>
          <small>
            Includes temporary source copies and processing headroom. Processing space is
            approximate and monitored during the job.
          </small>
          {plan.storage.blocked && (
            <p className="error" role="alert">
              Insufficient storage for this plan while keeping 20 GiB free. Free space or reduce the
              source plan before continuing.
            </p>
          )}
        </>
      )}
    </div>
  );
}
