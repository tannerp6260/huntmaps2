// Drafts belong to a tab, but remain recoverable from local storage after it closes.
// Keep their starting revision: loading a newer server record must not rebase a draft.
export type ReviewDraft = {
  notes: string;
  status: string;
  revision: number;
  updated: number;
};

let tab: string = crypto.randomUUID();
try {
  tab = sessionStorage.getItem('huntmaps-review-tab') || tab;
  sessionStorage.setItem('huntmaps-review-tab', tab);
} catch {
  // A fresh identity still isolates this document if session storage is unavailable.
}

// Duplicating a tab copies sessionStorage. Give the newcomer its own identity;
// reloading an existing tab keeps its identity and its unfinished draft.
export const reviewDraftsReady = new Promise<void>((resolve) => {
  let probing = true;
  const instance = crypto.randomUUID();
  try {
    const channel = new BroadcastChannel('huntmaps-review-tabs');
    channel.onmessage = ({ data }) => {
      if (data?.tab !== tab || data.instance === instance) return;
      if (data.kind === 'probe')
        channel.postMessage({ kind: 'occupied', tab, instance, target: data.instance });
      if (probing && data.kind === 'occupied' && data.target === instance) {
        tab = crypto.randomUUID();
        try {
          sessionStorage.setItem('huntmaps-review-tab', tab);
        } catch {
          /* The document identity still remains unique. */
        }
      }
    };
    channel.postMessage({ kind: 'probe', tab, instance });
  } catch {
    // Without cross-tab messaging, use a new document identity; earlier drafts
    // remain available through explicit recovery rather than risking a collision.
    tab = crypto.randomUUID();
  }
  setTimeout(() => {
    probing = false;
    resolve();
  }, 75);
});

function parse(raw: string | null): ReviewDraft | null {
  try {
    const value = JSON.parse(raw || 'null');
    if (
      typeof value?.notes !== 'string' ||
      !['unmarked', 'keep', 'reject', 'needs inspection'].includes(value.status) ||
      value.notes.length > 10000 ||
      !Number.isSafeInteger(value.revision ?? 0) ||
      (value.revision ?? 0) < 0
    )
      return null;
    return { ...value, revision: value.revision ?? 0, updated: value.updated || 0 };
  } catch {
    return null;
  }
}

export function readReviewDraft(base: string) {
  return parse(localStorage.getItem(`${base}:${tab}`)) || parse(localStorage.getItem(base));
}

export function otherReviewDrafts(base: string): ReviewDraft[] {
  const drafts: ReviewDraft[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key?.startsWith(base + ':') || key === `${base}:${tab}`) continue;
    const draft = parse(localStorage.getItem(key));
    if (draft) drafts.push(draft);
  }
  return drafts.sort((a, b) => b.updated - a.updated);
}

export function writeReviewDraft(base: string, draft: Omit<ReviewDraft, 'updated'>) {
  localStorage.setItem(`${base}:${tab}`, JSON.stringify({ ...draft, updated: Date.now() }));
}

export function acknowledgeReviewDraft(
  base: string,
  payload: { notes: string; status: string },
  revision: number,
) {
  const key = `${base}:${tab}`;
  const draft = parse(localStorage.getItem(key)) || parse(localStorage.getItem(base));
  if (draft && (draft.notes !== payload.notes || draft.status !== payload.status)) {
    // Only our own successful save can advance the base of edits made while saving.
    writeReviewDraft(base, { ...draft, revision });
    return true;
  }
  localStorage.removeItem(key);
  const legacy = parse(localStorage.getItem(base));
  if (legacy?.notes === payload.notes && legacy.status === payload.status)
    localStorage.removeItem(base);
  return false;
}
