// Product-level checks: use real saved terrain and isolated workflow records.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base = process.env.HUNTMAPS_URL, out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out) throw Error('Provide an isolated HUNTMAPS_URL and HUNTMAPS_SCREENSHOTS.');
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HUNTMAPS_BROWSER || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [], layouts = [];
page.on('pageerror', e => errors.push(e.message));
await page.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
await page.route('**/*', r => r.request().url().startsWith(base) || r.request().url().startsWith('blob:') ? r.continue() : r.abort());
const nav = page.getByRole('navigation', { name: 'Scouting workflow' });
const idle = () => page.waitForFunction(() => JSON.parse(document.querySelector('.map')?.dataset.mapState || '{}').loaded, undefined, { timeout: 90000 });
async function layout(label) {
  await idle();
  const size = await page.evaluate(() => {
    const map = document.querySelector('.map-pane').getBoundingClientRect();
    return { width: innerWidth, height: innerHeight, documentWidth: document.documentElement.scrollWidth, documentHeight: document.documentElement.scrollHeight, mapWidth: map.width, mapHeight: map.height };
  });
  assert.equal(size.documentWidth, size.width, 'No horizontal page overflow');
  assert.equal(size.documentHeight, size.height, 'The workspace stays within the viewport');
  assert.ok(size.mapWidth / size.width >= .73, 'The map has at least 73% of the desktop width');
  layouts.push({ label, ...size });
  await page.screenshot({ path: `${out}/${label}.png` });
}
try {
  await page.goto(base);
  await page.getByLabel('Run selector').selectOption('soap-creek-decision-review-v2');
  await page.getByLabel('Select A0075', { exact: true }).waitFor();
  const selected = await page.locator('.candidate.active .candidate-select strong').innerText();
  const first = await page.locator('.candidate-select strong').first().innerText();
  assert.equal(selected, first, 'Initial selection matches the leading ranked setup');
  for (const [width, height] of [[1920,1080],[1440,900],[1366,768]]) {
    await page.setViewportSize({ width, height });
    await layout(`find-${width}`);
  }
  await page.getByLabel('Select A0075', { exact: true }).click();
  assert.equal(await page.getByLabel('Select A0075', { exact: true }).getAttribute('aria-pressed'), 'true');
  await page.getByRole('button', { name: 'Selected map setup A0075', exact: true }).waitFor();
  await page.locator('.selected-setup').getByText('0.485 mi²', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Setup details', exact: true }).click();
  await page.getByLabel('Candidate notes').waitFor();
  await page.screenshot({ path: `${out}/setup-details-1366.png` });
  await page.getByRole('button', { name: '← All setups', exact: true }).click();
  await page.getByRole('button', { name: /Terrain & access filters/ }).click();
  await page.getByRole('button', { name: 'Apply review filters', exact: true }).waitFor();
  await page.getByRole('button', { name: '← All setups', exact: true }).click();
  await page.getByLabel('Find a setup').fill('no-matching-setup');
  await page.getByText('No matching setups', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Reset result filters', exact: true }).click();
  await page.getByLabel('Select A0075', { exact: true }).waitFor();
  await page.locator('.layers > summary').click();
  await page.getByLabel('Overlay opacity', { exact: true }).fill('0.35');
  await page.screenshot({ path: `${out}/layers-1366.png` });
  await page.locator('.layers > summary').click();
  await page.getByRole('button', { name: 'Expand map', exact: true }).click();
  await idle();
  assert.ok((await page.locator('.map-pane').boundingBox()).width > 1300);
  await page.getByRole('button', { name: 'Show scouting panel', exact: true }).click();
  await nav.getByRole('button', { name: /Save.*confirmed/ }).click();
  await page.getByText('Build your collection', { exact: true }).waitFor();
  await page.screenshot({ path: `${out}/collection-empty-1366.png` });
  // Existing completed fixture proves persistent collection/export and stage navigation.
  await page.getByLabel('Run selector').selectOption('workflow-fixture');
  await page.getByLabel('Select A0001', { exact: true }).waitFor();
  assert.equal(await nav.getByRole('button', { name: /Find/ }).getAttribute('aria-current'), 'step');
  await nav.getByRole('button', { name: /Save.*confirmed/ }).click();
  const saved = page.locator('.collection-item').filter({ hasText: 'A0001' });
  await saved.waitFor();
  const exportLink = saved.getByRole('link', { name: 'Waypoint GPX', exact: true });
  const download = await page.request.get(base + await exportLink.getAttribute('href'));
  assert.equal(download.status(), 200);
  assert.match(await download.text(), /<wpt/);
  await page.screenshot({ path: `${out}/saved-1366.png` });
  await page.reload();
  await page.getByLabel('Select A0001', { exact: true }).waitFor();
  assert.equal(await page.getByLabel('Run selector').inputValue(), 'workflow-fixture', 'Area survives reload');
  await nav.getByRole('button', { name: /Inspect.*terrain/ }).click();
  await page.getByRole('button', { name: 'Inspect current setup', exact: true }).click();
  await page.waitForFunction(() => JSON.parse(document.querySelector('.fp-scene')?.dataset.camera || '{}').loaded, undefined, {timeout:60000});
  await page.locator('.fp-orientation').getByText(/Observer A0001/).waitFor();
  await page.screenshot({ path: `${out}/inspect-1366.png` });
  await page.keyboard.press('Escape');
  await page.getByRole('dialog', { name: 'First-person modeled view' }).waitFor({ state: 'hidden' });
  await page.getByLabel('Run selector').selectOption('soap-creek-decision-review-v2');
  await page.getByLabel('Select A0075', { exact: true }).waitFor();
  assert.equal(await nav.getByRole('button', { name: /Find/ }).getAttribute('aria-current'), 'step', 'Changing areas exits stale inspection state');
  await page.getByRole('button', { name: '+ New area', exact: true }).click();
  await page.getByRole('button', { name: 'Draw boundary', exact: true }).waitFor();
  await page.screenshot({ path: `${out}/new-area-1366.png` });
  await page.getByRole('button', { name: 'Import file', exact: true }).click();
  await page.getByLabel('Import observer polygon').setInputFiles(process.env.HUNTMAPS_IMPORT_FILE || '../../inputs/test.kml');
  await page.getByLabel('Polygon selection').waitFor();
  await page.screenshot({ path: `${out}/imported-area-1366.png` });
  // An uncalculated manual waypoint must never inherit its anchor's visible area.
  const manualPage = await browser.newPage();
  await manualPage.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
  await manualPage.route('**/api/runs/soap-creek-decision-review-v2/manual-observers', route => route.fulfill({json:[{
    id:'manual-ux-check', name:'Uncalculated test position', anchor:'A0075',
    kind:'provisional-manual-observer', status:'unmarked', notes:'',
    latitude:38.686, longitude:-107.29, displacement_m:1, east_m:1, north_m:0,
    scene_y_m:0, scene_key:'test', ground_m:2800, analysis:'not calculated', access:'unknown'
  }]}));
  await manualPage.goto(base);
  await manualPage.getByLabel('Run selector').selectOption('soap-creek-decision-review-v2');
  await manualPage.getByLabel('Select waypoint Uncalculated test position', {exact:true}).click();
  await manualPage.locator('.selected-setup .selection-metric strong').getByText('unknown', {exact:true}).waitFor();
  await manualPage.close();
  const failedScene = await browser.newPage();
  await failedScene.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
  await failedScene.route('**/assets/first-person-*.js', route => route.abort());
  await failedScene.goto(base);
  await failedScene.getByRole('button', {name:'View', exact:true}).click();
  await failedScene.getByRole('dialog', {name:'View could not open', exact:true}).waitFor();
  await failedScene.getByRole('button', {name:'Return to map', exact:true}).click();
  await failedScene.getByRole('button', {name:'Setup details', exact:true}).waitFor();
  await failedScene.close();
  assert.deepEqual(errors, []);
  fs.writeFileSync(`${out}/results.json`, JSON.stringify({ layouts, errors, selectedSetup: true, persistentArea: true, collectionExport: true, stageReset: true, sceneReturn: true, polygonImport: true }, null, 2));
  console.log('Redesigned desktop layouts, selection, filters, layers, collection/export, scene and area recovery passed:', out);
} catch (e) {
  await page.screenshot({ path: `${out}/failure.png` });
  fs.writeFileSync(`${out}/failure.txt`, await page.locator('body').innerText());
  throw e;
} finally { await browser.close(); }
