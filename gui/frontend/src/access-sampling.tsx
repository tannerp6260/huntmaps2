import DecimalField from './decimal-field';
import { decimalValue } from './decimal-input';
import { Help } from './drawing';
import { networkResponse } from './network-response';
import { useEffect, useState } from 'react';
export type Sampling = {
  network_ids: string[];
  kinds: string[];
  distance_m: number | null;
  height_m: number | null;
};
export default function AccessSampling({
  onValidity,
  onChange,
  includeNetwork,
  onNetwork,
  initialSampling,
}: {
  onValidity: (valid: boolean) => void;
  onChange: (v: Sampling | null) => void;
  initialSampling: Sampling | null;
  includeNetwork: boolean;
  onNetwork: (v: boolean) => void;
}) {
  const [enabled, setEnabled] = useState(!!initialSampling),
    [distance, setDistance] = useState(String((initialSampling?.distance_m ?? 804.672) / 0.9144)),
    [heightEnabled, setHeightEnabled] = useState(initialSampling?.height_m != null),
    [height, setHeight] = useState(String((initialSampling?.height_m ?? 304.8) / 0.3048)),
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
        if (alive) {
          setNetworks(v);
          // Empty IDs let the reviewed analysis plan resolve covering inventories.
        }
      })
      .catch((e) => {
        if (alive) setNetworkError(String(e));
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    const valid =
      !enabled ||
      (kinds.length > 0 &&
        decimalValue(distance) !== null &&
        (!heightEnabled || decimalValue(height) !== null));
    onValidity(valid);
    if (!valid) return;
    onChange(
      enabled
        ? {
            network_ids: ids,
            kinds,
            distance_m: decimalValue(distance)! * 0.9144,
            height_m: heightEnabled ? decimalValue(height)! * 0.3048 : null,
          }
        : null,
    );
  }, [enabled, distance, heightEnabled, height, ids, kinds]);
  return (
    <details>
      <summary>Road and trail restrictions</summary>
      {networkError && <p className="error">{networkError}</p>}
      <p className="hint">
        Roads and trails are included in the source plan; verified cached data is reused.
      </p>{' '}
      <label>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Only look near mapped roads or trails
      </label>
      {enabled && !ids.length && (
        <p className={includeNetwork ? 'hint' : 'error'}>
          {includeNetwork
            ? 'Sampling will use networks acquired or reused by this reviewed plan.'
            : 'Select at least one source dataset, or include the reviewed USFS acquisition.'}
        </p>
      )}
      {enabled && !kinds.length && <p className="error">Choose Roads, Trails, or both.</p>}
      {enabled &&
        (decimalValue(distance) === null || (heightEnabled && decimalValue(height) === null)) && (
          <p className="error">Enter a complete nonnegative distance before generating setups.</p>
        )}
      {enabled && (
        <>
          <p className="hint">
            Only test places within the distance below. This is straight-line proximity, not walking
            distance or permission.
          </p>
          <fieldset>
            <legend>Mapped feature types to use</legend>
            <p className="hint">Choose which mapped features qualify a place for sampling.</p>
            {['roads', 'trails'].map((k) => (
              <label key={k}>
                <input
                  type="checkbox"
                  checked={kinds.includes(k)}
                  onChange={(e) =>
                    setKinds((v) => (e.target.checked ? [...v, k] : v.filter((i) => i !== k)))
                  }
                />
                {k === 'roads' ? 'Roads' : 'Trails'}
              </label>
            ))}
          </fieldset>
          <details>
            <summary>Advanced source datasets</summary>
            <p>
              These are the inventories supplying mapped features. The Roads and Trails choices
              above determine which feature types qualify. Only observer eligibility changes; your
              polygon, target terrain and obstruction terrain stay intact. Unknown network or
              elevation does not qualify.
            </p>
            <p className="hint">
              With no dataset selected, use the networks acquired or reused for this run.
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
                {n.kind === 'roads'
                  ? 'Road dataset'
                  : n.kind === 'trails'
                    ? 'Trail dataset'
                    : n.kind + ' dataset'}
                :{' '}
                {n.source.startsWith('https://apps.fs.usda.gov/')
                  ? 'USFS mapped inventory'
                  : n.source}
              </label>
            ))}
          </details>{' '}
          <label>
            Maximum distance from a road or trail (yards) <Help topic="proximity" />
            <DecimalField
              aria-label="Maximum distance from a road or trail (yards)"
              value={decimalValue(distance) ?? NaN}
              onChange={(n) => setDistance(Number.isFinite(n) ? String(n) : '')}
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
              <DecimalField
                aria-label="Maximum height above network (feet)"
                value={decimalValue(height) ?? NaN}
                onChange={(n) => setHeight(Number.isFinite(n) ? String(n) : '')}
              />
            </label>
          )}
        </>
      )}
    </details>
  );
}
