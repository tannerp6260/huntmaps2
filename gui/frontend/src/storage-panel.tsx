import { useState } from 'react';
import { refreshPolling } from './polling';
type Status = {
  state_dir: string;
  records: number;
  problems: string[];
  backups: { id: string; created: number }[];
};
type Inventory = {
  total_bytes: number;
  reclaimable_bytes: number;
  items: { path: string; kind: string; bytes: number; protected: boolean; reason: string }[];
};
type Preview = { token: string; selected: string[]; reclaimable_bytes: number };
async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    '/api/storage' + path,
    body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-HuntMaps': 'local' },
          body: JSON.stringify(body),
        },
  );
  const value = await response.json();
  if (!response.ok) throw Error(value.detail || response.statusText);
  if (body !== undefined) void refreshPolling();
  return value as T;
}
export default function StoragePanel({ onRecordsChanged }: { onRecordsChanged: () => void }) {
  const [status, setStatus] = useState<Status | null>(null),
    [inventory, setInventory] = useState<Inventory | null>(null),
    [preview, setPreview] = useState<Preview | null>(null),
    [message, setMessage] = useState(''),
    [confirmation, setConfirmation] = useState(''),
    [selected, setSelected] = useState(''),
    [busy, setBusy] = useState(false);
  const refresh = async () => {
    const [status, inventory] = await Promise.all([call<Status>(''), call<Inventory>('/cache')]);
    setStatus(status);
    setInventory(inventory);
  };
  const action = async (fn: () => Promise<unknown>, records = false, clearPreview = true) => {
    setBusy(true);
    try {
      const result = await fn();
      setMessage(JSON.stringify(result));
      if (clearPreview) setPreview(null);
      await refresh();
      if (records) onRecordsChanged();
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <details
      className="storage-panel"
      onToggle={(event) => {
        if (event.currentTarget.open) void refresh().catch((error) => setMessage(String(error)));
      }}
    >
      <summary>Storage and recovery</summary>
      <p>
        {status?.records || 0} saved record files. Backups retain notes, coordinates and waypoint
        revisions.
      </p>
      {status?.problems.map((problem) => (
        <p key={problem} role="alert">
          {problem}
        </p>
      ))}
      <button disabled={busy} onClick={() => action(() => call('/backup', {}))}>
        Back up GUI records
      </button>
      <label>
        Record backup
        <select
          aria-label="Record backup"
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
        >
          <option value="">Choose backup…</option>
          {status?.backups.map((backup) => (
            <option key={backup.id} value={backup.id}>
              {new Date(backup.created * 1000).toLocaleString()} · {backup.id.slice(0, 8)}
            </option>
          ))}
        </select>
      </label>
      <button
        disabled={busy || !selected}
        onClick={() => action(() => call('/restore', { backup: selected }), true)}
      >
        Restore selected backup
      </button>
      <p>
        {((inventory?.total_bytes || 0) / 1048576).toFixed(1)} MB cached;{' '}
        {((inventory?.reclaimable_bytes || 0) / 1048576).toFixed(1)} MB eligible for cleanup.
      </p>
      <button
        disabled={busy}
        onClick={() =>
          action(
            async () => {
              const value = await call<Preview>('/cache/preview', {});
              setPreview(value);
              return { preview_bytes: value.reclaimable_bytes };
            },
            false,
            false,
          )
        }
      >
        Preview cache cleanup
      </button>
      {preview && (
        <>
          <p>
            {preview.selected.length} cache entries ·{' '}
            {(preview.reclaimable_bytes / 1048576).toFixed(1)} MB. Referenced scenes and waypoint
            masks are retained.
          </p>
          <button
            disabled={busy}
            onClick={() => action(() => call('/cache/cleanup', { token: preview.token }))}
          >
            Clean previewed cache
          </button>
        </>
      )}
      <details>
        <summary>Reset notes and waypoints</summary>
        <p>This resets GUI notes and waypoints, and retains a backup. Type RESET GUI RECORDS.</p>
        <input
          aria-label="Reset confirmation"
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
        />
        <button
          disabled={busy || confirmation !== 'RESET GUI RECORDS'}
          onClick={() => action(() => call('/reset', { confirmation }), true)}
        >
          Reset GUI records
        </button>
      </details>
      <p role="status">{message}</p>
      <small>State: {status?.state_dir}</small>
    </details>
  );
}
