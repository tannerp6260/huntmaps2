import { networkResponse } from './network-response';
import { useEffect, useState } from 'react';
export type Sampling = {
  network_ids: string[];
  kinds: string[];
  distance_m: number | null;
  height_m: number | null;
};
export default function AccessSampling({
  onChange,
  includeNetwork,
  onNetwork,
  initialSampling,
}: {
  onChange: (v: Sampling | null) => void;
  initialSampling: Sampling | null;
  includeNetwork: boolean;
  onNetwork: (v: boolean) => void;
}) {
  const [enabled, setEnabled] = useState(!!initialSampling),
    [distance, setDistance] = useState((initialSampling?.distance_m ?? 804.672) / 1609.344),
    [heightEnabled, setHeightEnabled] = useState(initialSampling?.height_m != null),
    [height, setHeight] = useState((initialSampling?.height_m ?? 304.8) / 0.3048),
    [ids, setIds] = useState<string[]>(initialSampling?.network_ids || []),
    [kinds, setKinds] = useState(initialSampling?.kinds || ['roads', 'trails']),
    [networks, setNetworks] = useState<{ id: string; kind: string; source: string }[]>([]);
  const [networkError, setNetworkError] = useState('');
  useEffect(() => {
    let alive = true;
    fetch('/api/networks')
      .then(async (r) => {
        const v = await r.json();
        if (!r.ok) throw Error(v.detail || 'Network records unavailable');
        return v;
      })
      .then(networkResponse)
      .then((v) => {
        if (alive) setNetworks(v);
      })
      .catch((e) => {
        if (alive) setNetworkError(String(e));
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    onChange(
      enabled
        ? {
            network_ids: ids,
            kinds,
            distance_m: distance * 1609.344,
            height_m: heightEnabled ? height * 0.3048 : null,
          }
        : null,
    );
  }, [enabled, distance, heightEnabled, height, ids, kinds]);
  return (
    <details>
      <summary>Observer access sampling and network acquisition</summary>
      {networkError && <p className="error">{networkError}</p>}
      <label>
        <input
          type="checkbox"
          checked={includeNetwork}
          onChange={(e) => onNetwork(e.target.checked)}
        />
        Include bounded USFS roads/trails in this reviewed download plan (up to 20 MB, shared cap)
      </label>
      <label>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Constrain new observer sampling by loaded network proximity
      </label>
      {enabled && (
        <>
          <p>
            Only observer eligibility changes. Original polygon, targets and obstruction terrain
            stay intact. Unknown network/elevation does not qualify. Import or acquire networks in
            review first.
          </p>
          {networks.map((n) => (
            <label key={n.id}>
              <input
                type="checkbox"
                checked={ids.includes(n.id)}
                onChange={(e) =>
                  setIds((v) => (e.target.checked ? [...v, n.id] : v.filter((id) => id !== n.id)))
                }
              />
              {n.kind}: {n.source}
            </label>
          ))}
          {['roads', 'trails'].map((k) => (
            <label key={k}>
              <input
                type="checkbox"
                checked={kinds.includes(k)}
                onChange={(e) =>
                  setKinds((v) => (e.target.checked ? [...v, k] : v.filter((i) => i !== k)))
                }
              />
              {k}
            </label>
          ))}
          <label>
            Maximum proximity (miles)
            <input
              type="number"
              min="0"
              value={distance}
              onChange={(e) => setDistance(+e.target.value)}
            />
          </label>
          <label>
            <input
              type="checkbox"
              checked={heightEnabled}
              onChange={(e) => setHeightEnabled(e.target.checked)}
            />
            Limit height above nearest mapped line
          </label>
          {heightEnabled && (
            <label>
              Maximum height (feet)
              <input
                type="number"
                min="0"
                value={height}
                onChange={(e) => setHeight(+e.target.value)}
              />
            </label>
          )}
        </>
      )}
    </details>
  );
}
