import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
if (!process.env.HUNTMAPS_URL || !process.env.HUNTMAPS_SCREENSHOTS) throw Error('Run via isolated ./gui/check');
const base = process.env.HUNTMAPS_URL, out = process.env.HUNTMAPS_SCREENSHOTS;
fs.mkdirSync(out, { recursive: true });
const { networkResponse } = await import('data:text/javascript;base64,' + Buffer.from(ts.transpileModule(fs.readFileSync('src/network-response.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText).toString('base64'));
const browser = await chromium.launch({ executablePath: process.env.HUNTMAPS_BROWSER || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
  await page.route('**/*', r => r.request().url().startsWith(base) || r.request().url().startsWith('blob:') ? r.continue() : r.abort());
  const point = await (await page.request.get(base + '/api/runs/soap-creek-decision-review-v2/candidates/A0075')).json();
  const { longitude: lon, latitude: lat } = point;
  const legacy = ['roads', 'trails'].map((kind, index) => ({
    id: String(index + 1).repeat(32), kind, source: 'Synthetic legacy network', source_date: 'unknown', coverage: null,
    lines: [{ type: 'LineString', coordinates: [[lon + index * .001, lat - .002], [lon + index * .001, lat + .002]] }],
  }));
  const original = JSON.stringify(legacy);
  const converted = networkResponse(legacy);
  assert.deepEqual(converted.map(n => n.lines), legacy.map(n => n.lines));
  assert.ok(converted.every(n => n.display_features[0].properties.subtype === 'unknown'));
  assert.equal(JSON.stringify(legacy), original);
  assert.throws(() => networkResponse({ networks: legacy }), /network list/);
  let mode = 'empty', jobs = [];
  const planId = 'abcdefabcdefabcdefabcdefabcdefab';
  await page.route('**/api/jobs', route => route.fulfill({ json: jobs }));
  await page.route('**/api/networks', route => {
    if (mode === 'failure') return route.fulfill({ status: 503, json: { detail: 'Synthetic network service failure' } });
    const records = mode === 'empty' ? [] : mode === 'malformed' ? [{ id: 'broken', kind: 'roads', display_features: [null] }] : mode === 'legacy' ? legacy : legacy.map(n => ({ ...n, display_features: n.lines.map(geometry => ({ type: 'Feature', geometry, properties: { kind: n.kind, subtype: n.kind === 'roads' ? 'gravel' : 'motorized' } })) }));
    return route.fulfill({ json: records });
  });
  await page.route('**/api/network-plans', route => route.fulfill({ json: { id: planId, provider: 'Synthetic reviewed network download', estimated_bytes: 20000000, note: 'Synthetic response', bounds: route.request().postDataJSON().bounds } }));
  await page.route(`**/api/network-plans/${planId}/start`, route => {
    assert.equal(route.request().postDataJSON().download, true);
    mode = 'legacy';
    jobs = [{ id: '11223344556677889900112233445566', kind: 'network-acquisition', plan: planId, status: 'complete', stage: 'Finished', elapsed_s: 1 }];
    return route.fulfill({ json: jobs[0] });
  });
  await page.goto(base);
  const controls = page.locator('.network-map-controls');
  await controls.getByText('No road/trail data loaded.', { exact: false }).waitFor();
  await controls.getByRole('button', { name: 'Review road/trail download', exact: true }).click();
  await controls.getByLabel('Approve this reviewed network download', { exact: true }).check();
  await controls.getByRole('button', { name: 'Download mapped roads/trails', exact: true }).click();
  await controls.getByText('Unknown road surface', { exact: true }).waitFor();
  await controls.getByText('Unknown trail use', { exact: true }).waitFor();
  await controls.getByText('Network acquisition complete:', { exact: false }).waitFor();
  assert.ok((await page.locator('#root').innerText()).includes('HuntMaps2'));
  await page.getByRole('button', { name: 'View from this setup', exact: true }).waitFor();
  await page.waitForTimeout(800);
  await controls.getByText('Unknown road surface', { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: out + '/01-legacy-download-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 900, height: 900 });
  await page.screenshot({ path: out + '/02-legacy-download-900.png', fullPage: true });
  const refresh = async () => page.evaluate(() => window.dispatchEvent(new Event('huntmaps-networks-changed')));
  mode = 'current'; await refresh();
  await controls.getByText('Gravel road', { exact: true }).waitFor();
  await controls.getByText('Recorded motorized trail', { exact: true }).waitFor();
  mode = 'malformed'; await refresh();
  await controls.getByRole('alert').filter({ hasText: 'display geometry is invalid' }).waitFor();
  assert.ok((await page.locator('#root').innerText()).includes('HuntMaps2'));
  // A full reload also exercises the review panel's network-list consumer.
  await page.reload();
  await controls.getByRole('alert').filter({ hasText: 'display geometry is invalid' }).waitFor();
  assert.ok((await page.locator('#root').innerText()).includes('HuntMaps2'));
  await page.getByRole('button', { name: 'View from this setup', exact: true }).waitFor();
  mode = 'failure'; await refresh();
  await controls.getByRole('alert').filter({ hasText: 'Synthetic network service failure' }).waitFor();
  await controls.getByRole('alert').scrollIntoViewIfNeeded();
  await page.screenshot({ path: out + '/03-network-error-900.png', fullPage: true });
  mode = 'current'; await refresh();
  await controls.getByText('Gravel road', { exact: true }).waitFor();
  assert.equal(await controls.getByRole('alert').count(), 0);
  assert.deepEqual(errors, []);
  console.log('Successful download with legacy network response, exact geometry, current metadata, empty data, malformed responses and network failure recovery passed');
} finally { await browser.close(); }
