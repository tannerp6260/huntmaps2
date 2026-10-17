import { useSyncExternalStore } from 'react';
import type { Job } from './types';

let jobs: Job[] = [];
const versions = new Map<string, number>();
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setTimeout> | undefined;
let pending: Promise<void> | undefined;
let controller: AbortController | undefined;
export const jobSnapshot = () => jobs;
export function trackJob(job: Job) {
  job = {
    ...job,
    elapsed_s: job.elapsed_s ?? 0,
    logs: job.logs ?? '',
    stage: job.stage || 'Starting…',
  };
  versions.set(job.id, (versions.get(job.id) || 0) + 1);
  if (versions.size > 200) {
    for (const id of versions.keys()) {
      if (!jobs.some((j) => j.id === id)) versions.delete(id);
      if (versions.size <= 200) break;
    }
  }
  jobs = [job, ...jobs.filter((j) => j.id !== job.id)];
  for (const listener of listeners) listener();
  void refreshPolling();
}

export function refreshPolling(): Promise<void> {
  if (pending) return pending;
  clearTimeout(timer);
  controller = new AbortController();
  const active = jobs.filter((j) => ['running', 'cancelling'].includes(j.status));
  const requestedVersions = new Map(versions);
  const read = async (path: string) => {
    const response = await fetch(path, { signal: controller!.signal });
    if (!response.ok) throw Error('Cannot refresh jobs');
    return response.json();
  };
  pending = (
    active.length
      ? Promise.all(active.map((j) => read('/api/jobs/' + j.id))).then((values) => {
          jobs = jobs.map((j) =>
            versions.get(j.id) !== requestedVersions.get(j.id)
              ? j
              : values.find((v) => v.id === j.id) || j,
          );
        })
      : read('/api/jobs').then((values) => {
          const recent = jobs.filter((j) => versions.get(j.id) !== requestedVersions.get(j.id));
          jobs = [...recent, ...values.filter((j: Job) => !recent.some((v) => v.id === j.id))];
        })
  )
    .then(() => {
      for (const listener of listeners) listener();
    })
    .catch((error: unknown) => {
      if (!(error instanceof DOMException && error.name === 'AbortError')) console.error(error);
    })
    .finally(() => {
      pending = undefined;
      if (listeners.size)
        timer = setTimeout(
          refreshPolling,
          jobs.some((job) => ['running', 'cancelling'].includes(job.status)) ? 1000 : 5000,
        );
    });
  return pending;
}

export function subscribePolling(listener: () => void) {
  listeners.add(listener);
  listener();
  void refreshPolling();
  return () => {
    listeners.delete(listener);
    if (!listeners.size) {
      clearTimeout(timer);
      controller?.abort();
    }
  };
}
export function useJobs() {
  return useSyncExternalStore(subscribePolling, jobSnapshot);
}
