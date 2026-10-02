import { useState } from 'react';
export default function JobLogs({
  id,
  label = 'Actual subprocess log',
}: {
  id: string;
  label?: string;
}) {
  const [logs, setLogs] = useState(''),
    [error, setError] = useState('');
  return (
    <details
      onToggle={(event) => {
        if (event.currentTarget.open)
          fetch(`/api/jobs/${id}/logs`)
            .then(async (response) => {
              if (!response.ok) throw Error('Cannot load job log');
              setLogs((await response.json()).logs);
            })
            .catch((error: unknown) =>
              setError(error instanceof Error ? error.message : String(error)),
            );
      }}
    >
      <summary>{label}</summary>
      <pre>{error || logs}</pre>
    </details>
  );
}
