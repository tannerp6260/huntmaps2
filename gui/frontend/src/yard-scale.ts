import type { Map, IControl } from 'maplibre-gl';
import { METERS_PER_YARD } from './units';
// Public projection APIs keep this correct at the current zoom and latitude.
export class YardScale implements IControl {
  private map?: Map;
  private element = document.createElement('div');
  private update = () => {
    const map = this.map;
    if (!map) return;
    const y = map.getContainer().clientHeight / 2;
    const a = map.unproject([10, y]),
      b = map.unproject([110, y]);
    const distance = a.distanceTo(b) / METERS_PER_YARD;
    if (!Number.isFinite(distance) || distance <= 0) return;
    const base = Math.pow(10, Math.floor(Math.log10(distance)));
    const ticks = [1, 2, 5].map((n) => n * base);
    const chosen = ticks.filter((n) => n <= distance).at(-1) || base / 2;
    this.element.style.width = `${(100 * chosen) / distance}px`;
    this.element.textContent = `${chosen.toLocaleString()} yd`;
  };
  onAdd(map: Map) {
    this.map = map;
    this.element.className = 'maplibregl-ctrl maplibregl-ctrl-scale';
    map.on('move', this.update);
    map.on('resize', this.update);
    this.update();
    return this.element;
  }
  onRemove() {
    this.map?.off('move', this.update);
    this.map?.off('resize', this.update);
    this.element.remove();
    this.map = undefined;
  }
}
