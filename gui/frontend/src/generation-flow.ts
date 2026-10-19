import type { BaselinePlan, Job } from './types';

export type GenerationIntent = { cancelled: boolean; planId?: string; jobId?: string };
type Api = (path: string, options?: RequestInit) => Promise<any>;

export function generationBlocker(plan: BaselinePlan): string | null {
  if (plan.storage?.blocked)
    return 'Not enough free storage. Review storage before generating setups.';
  if (plan.acquisition?.errors?.length) return plan.acquisition.errors.join('\n');
  if ((plan.acquisition?.estimated_bytes || 0) > plan.max_download_mb * 1e6)
    return `Estimated download exceeds the ${plan.max_download_mb} MB cap. Increase the transfer limit explicitly or use a smaller area with a new run name.`;
  return null;
}

// Intent lives only in this page. A reload can recover jobs, but cannot authorize a new start.
export async function generateSetups(
  api: Api,
  intent: GenerationIntent,
  options: {
    inputs?: Record<string, unknown>;
    existingPlan?: string;
    onPlan: (id: string, plan?: BaselinePlan) => void;
    onJob: (job: Job) => void;
    onStarted: (id: string) => void;
  },
) {
  if (intent.cancelled) return;
  let preparing = !options.existingPlan;
  if (options.existingPlan) {
    intent.planId = options.existingPlan;
    const plan = await api(`/plans/${intent.planId}`);
    if (intent.cancelled) return;
    if (plan.source_refresh_error) throw Error(plan.source_refresh_error);
    if (!plan.prepared || plan.source_refresh_required) {
      const job = await api(`/plans/${intent.planId}/prepare`, { method: 'POST' });
      intent.jobId = job.id;
      preparing = true;
      if (intent.cancelled) {
        await api(`/jobs/${job.id}/cancel`, { method: 'POST' });
        return;
      }
      options.onJob(job);
    }
  } else {
    const job = await api('/plans', { method: 'POST', body: JSON.stringify(options.inputs) });
    intent.planId = job.plan;
    intent.jobId = job.id;
    if (intent.cancelled) {
      await api(`/jobs/${job.id}/cancel`, { method: 'POST' });
      return;
    }
    options.onPlan(job.plan);
    options.onJob(job);
  }
  while (!intent.cancelled) {
    let [plan, job] = await Promise.all([
      api(`/plans/${intent.planId}`),
      intent.jobId ? api(`/jobs/${intent.jobId}`) : Promise.resolve(null),
    ]);
    if (intent.cancelled) return;
    // The completed job may be newer than the concurrent plan read. Verify a
    // fresh plan before declaring incomplete preparation or authorizing a start.
    if (job?.status === 'complete' && !plan.prepared) {
      plan = await api(`/plans/${intent.planId}`);
      if (intent.cancelled) return;
    }

    if (job) {
      intent.jobId = job.id;
      options.onJob(job);
    }
    options.onPlan(intent.planId!, plan);
    if (job && ['failed', 'cancelled', 'interrupted'].includes(job.status) && preparing)
      throw Error(
        job.failure_code === 'provider_failed'
          ? 'The source provider returned an error. Verified downloads are retained; retry the missing data.'
          : job.error || 'Source preparation stopped. Review the source plan to recover.',
      );
    if (job && ['running', 'cancelling'].includes(job.status)) throwIfRunningAnalysis(job);
    if (plan.prepared && (!job || !['running', 'cancelling'].includes(job.status))) {
      if (plan.source_refresh_required)
        throw Error(
          'The vegetation source plan is still outdated. Retry to refresh it before downloading.',
        );
      const blocker = generationBlocker(plan);
      if (blocker) throw Error(blocker);
      if (!plan.review_signature)
        throw Error('The source plan is unavailable. Refresh the plan before retrying.');
      if (intent.cancelled) return;
      const started = await api(`/plans/${intent.planId}/start`, {
        method: 'POST',
        body: JSON.stringify({ download: true, review_signature: plan.review_signature }),
      });
      intent.jobId = started.id;
      if (intent.cancelled) {
        await api(`/jobs/${started.id}/cancel`, { method: 'POST' });
        return;
      }
      options.onJob(started);
      options.onStarted(intent.planId!);
      return;
    }
    if (job?.status === 'complete' && !plan.prepared)
      throw Error('Source preparation is incomplete. Retry to refresh the source plan.');
    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
}

function throwIfRunningAnalysis(job: Job) {
  if (job.kind !== 'prepare')
    throw Error('This plan already has an active job. Follow its progress in Activity.');
}
