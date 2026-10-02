import { useSyncExternalStore } from 'react';
import type { Job } from './types';

let jobs: Job[] = [];
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setTimeout> | undefined;
let pending: Promise<void> | undefined;
let controller: AbortController | undefined;
export const jobSnapshot = () => jobs;

export function refreshPolling(): Promise<void> {
  if (pending) return pending;
  clearTimeout(timer);
  controller = new AbortController();
  pending = fetch('/api/jobs', { signal: controller.signal })
    .then(async (response) => {
      if (!response.ok) throw Error('Cannot refresh jobs');
      jobs = (await response.json()) as Job[];
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
