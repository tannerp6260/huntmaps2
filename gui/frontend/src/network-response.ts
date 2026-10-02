export type DisplayNetwork = {
  id: string;
  kind: 'roads' | 'trails';
  source: string;
  source_date: string;
  coverage_note: string;
  lines: GeoJSON.LineString[];
  coverage: number[] | null;
  display_features: GeoJSON.Feature<GeoJSON.LineString>[];
};
const line = (value: any): value is GeoJSON.LineString =>
  value?.type === 'LineString' &&
  Array.isArray(value.coordinates) &&
  value.coordinates.length >= 2 &&
  value.coordinates.every(
    (p: any) => Array.isArray(p) && p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
  );
const text = (value: unknown) => (typeof value === 'string' && value ? value : 'unknown');
export function networkResponse(value: unknown): DisplayNetwork[] {
  if (!Array.isArray(value)) throw Error('Invalid road/trail response; expected a network list.');
  return value.map((record) => {
    if (!record || typeof record.id !== 'string' || !['roads', 'trails'].includes(record.kind))
      throw Error('Invalid road/trail network record.');
    const kind = record.kind as DisplayNetwork['kind'];
    const properties = {
      kind,
      subtype: 'unknown',
      source: text(record.source),
      source_date: text(record.source_date),
      retrieved_utc: text(record.retrieved_utc),
    };
    let features: GeoJSON.Feature<GeoJSON.LineString>[];
    if (record.display_features == null) {
      if (!Array.isArray(record.lines) || !record.lines.every(line))
        throw Error('Road/trail line geometry is missing or invalid.');
      // Older running backends return sealed geometry without display metadata.
      features = record.lines.map((geometry: GeoJSON.LineString) => ({
        type: 'Feature',
        geometry,
        properties: { ...properties },
      }));
    } else {
      if (
        !Array.isArray(record.display_features) ||
        !record.display_features.every((f: any) => f?.type === 'Feature' && line(f.geometry))
      )
        throw Error('Road/trail display geometry is invalid.');
      const subtypes =
        kind === 'roads' ? ['paved', 'gravel', 'natural', 'other'] : ['motorized', 'nonmotorized'];
      features = record.display_features.map((f: GeoJSON.Feature<GeoJSON.LineString>) => ({
        ...f,
        properties: {
          ...properties,
          ...f.properties,
          kind,
          subtype: subtypes.includes(f.properties?.subtype) ? f.properties?.subtype : 'unknown',
        },
      }));
    }
    return {
      id: record.id,
      source: text(record.source),
      source_date: text(record.source_date),
      coverage_note: text(record.coverage_note),
      lines: features.map((f) => f.geometry),
      kind,
      display_features: features,
      coverage:
        Array.isArray(record.coverage) &&
        record.coverage.length === 4 &&
        record.coverage.every(Number.isFinite)
          ? record.coverage
          : null,
    };
  });
}
