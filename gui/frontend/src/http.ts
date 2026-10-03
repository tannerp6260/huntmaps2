import { refreshPolling } from './polling';
export async function request(path: string, body?: unknown, method = 'POST') {
  const r = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method,
          headers: { 'Content-Type': 'application/json', 'X-HuntMaps': 'local' },
          body: JSON.stringify(body),
        },
  );
  if (!r.ok) {
    let v;
    try {
      v = (await r.json()).detail;
    } catch {
      v = r.statusText;
    }
    throw Error(v);
  }
  const result = await r.json();
  if (body !== undefined) void refreshPolling();
  return result;
}
