import { useEffect, useState, useRef } from 'react';
type Entry = { id: string; label: string; archived: boolean };
type Preview = { token: string; bytes: number; paths: string[]; retained: string; files: number };
export default function RunManagement({
  api,
  onChanged,
}: {
  api: (path: string, options?: RequestInit) => Promise<any>;
  onChanged: () => void;
}) {
  const dialog = useRef<HTMLElement>(null);
  const [open, setOpen] = useState(false),
    [runs, setRuns] = useState<Entry[]>([]),
    [selected, setSelected] = useState(''),
    [preview, setPreview] = useState<Preview | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const refresh = async () => {
    setRuns(await api('/run-management'));
    setPreview(null);
  };
  useEffect(() => {
    if (open) void refresh().catch((e) => setError(String(e)));
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) {
        setOpen(false);
        return;
      }
      if (e.key !== 'Tab') return;
      const controls = [
        ...(dialog.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), select, input, summary',
        ) || []),
      ].filter((el) => el.getClientRects().length);
      const first = controls[0],
        last = controls.at(-1);
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    dialog.current?.querySelector<HTMLElement>('select')?.focus();
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('keydown', key);
      before?.focus();
    };
  }, [open, busy]);
  async function action(kind: string) {
    setBusy(true);
    setError('');
    try {
      if (kind === 'preview')
        setPreview(await api(`/run-management/${selected}/deletion-preview`, { method: 'POST' }));
      else {
        await api(`/run-management/${selected}/${kind === 'delete' ? 'delete' : 'archive'}`, {
          method: 'POST',
          body: JSON.stringify(
            kind === 'delete' ? { token: preview?.token } : { archived: kind === 'archive' },
          ),
        });
        await refresh();
        onChanged();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button onClick={() => setOpen(true)}>Manage saved results</button>
      {open && (
        <div className="fp-backdrop">
          <section
            ref={dialog}
            className="management-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Manage saved results"
          >
            <h2>Manage saved results</h2>
            <p>
              Archive hides a run from the selector. Permanent deletion removes only eligible
              generated results after review.
            </p>
            <select
              aria-label="Managed run"
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                setPreview(null);
                setError('');
              }}
            >
              <option value="">Choose a saved run…</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                  {r.archived ? ' · archived' : ''}
                </option>
              ))}
            </select>
            <div className="row">
              <button
                disabled={!selected || busy}
                onClick={() =>
                  action(runs.find((r) => r.id === selected)?.archived ? 'unarchive' : 'archive')
                }
              >
                {runs.find((r) => r.id === selected)?.archived ? 'Unarchive' : 'Archive'}
              </button>
              <button disabled={!selected || busy} onClick={() => action('preview')}>
                Review permanent deletion
              </button>
            </div>
            {preview && (
              <div className="notice">
                <p>
                  Delete {selected}: {preview.files} files, approximately{' '}
                  {(preview.bytes / 1e6).toFixed(1)} MB.
                </p>
                <p>{preview.retained}</p>
                <details>
                  <summary>Owned files and records</summary>
                  {preview.paths.map((p) => (
                    <p key={p}>{p}</p>
                  ))}
                </details>
                <button disabled={busy} onClick={() => action('delete')}>
                  Permanently delete these results
                </button>
              </div>
            )}
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <button onClick={() => setOpen(false)} disabled={busy}>
              Close
            </button>
          </section>
        </div>
      )}
    </>
  );
}
