import { openExisting, reloadExisting } from './browser-startup.mjs';
import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const base = process.env.HUNTMAPS_URL,
  out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out) throw Error('Run through ./gui/check');
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.HUNTMAPS_BROWSER || '/usr/bin/google-chrome',
  headless: true,
  args: [
    '--no-sandbox',
    '--enable-unsafe-swiftshader',
    '--use-gl=angle',
    '--use-angle=swiftshader',
  ],
});
const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
const errors = [],
  coverage = [],
  timings = [];
let tracking = false;
page.on('pageerror', (e) => errors.push(e.message));
page.on('request', (r) => {
  if (tracking && /\/(?:visible|classes)\/|\/collection-tiles\//.test(r.url()))
    coverage.push(r.url());
});
await page.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
await page.route('**/*', (route) =>
  route.request().url().startsWith(base) || route.request().url().startsWith('blob:')
    ? route.continue()
    : route.abort(),
);
const api = base + '/api/runs/search-fixture',
  headers = { 'X-HuntMaps': 'local' };
async function workflow() {
  return (await page.request.get(api + '/workflow')).json();
}
async function decide(cid, action) {
  const state = await workflow(),
    point =
      state.points[cid]?.point ||
      (await (await page.request.get(api + '/workflow-point/' + cid)).json());
  const response = await page.request.put(api + '/workflow/' + cid, {
    headers,
    data: { revision: state.revision, point, action },
  });
  assert.equal(response.status(), 200, await response.text());
}
try {
  const run = await (await page.request.get(api)).json();
  const ids = run.candidates.slice(0, 3).map((p) => p.id);
  assert.equal(ids.length, 3);
  const original = await workflow();
  assert.equal(
    Object.values(original.points).some((p) => p.shortlisted),
    false,
    'Use an independent fixture with no existing shortlist',
  );
  for (const cid of ids) await decide(cid, 'shortlist');
  await openExisting(page, base);
  await page.getByLabel('Run selector').selectOption('search-fixture');
  await page
    .getByRole('navigation', { name: 'Scouting workflow' })
    .getByRole('button', { name: /Approach/ })
    .click();
  await page.getByLabel('Focused approach spot').waitFor();
  tracking = true;
  const order = await page
    .getByLabel('Focused approach spot')
    .locator('option')
    .evaluateAll((options) => options.map((o) => o.value));
  await page.getByLabel('Focused approach spot').selectOption(order[0]);
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  await page.route(api + '/workflow/*', async (route) => {
    if (route.request().method() === 'PUT' && route.request().postDataJSON()?.action === 'dismiss')
      await gate;
    await route.continue();
  });
  for (let i = 0; i < order.length; i++) {
    const started = Date.now();
    await page.getByRole('button', { name: 'Dismiss spot & next', exact: true }).click();
    if (i < order.length - 1) {
      await page.waitForFunction(
        (id) => document.querySelector('[aria-label="Focused approach spot"]')?.value === id,
        order[i + 1],
        { timeout: 1500 },
      );
      assert.equal(
        await page.getByLabel('Focused approach spot').locator('option').count(),
        order.length - i - 1,
      );
    } else
      await page
        .getByText('No spots remain on the shortlist.', { exact: false })
        .waitFor({ timeout: 1500 });
    timings.push(Date.now() - started);
  }
  assert.equal(
    await page.locator('.map-setup-label').count(),
    0,
    'The last dismissed map label disappears immediately',
  );
  assert.ok(await page.getByText('Saving dismissal…', { exact: true }).isVisible());
  const pending = await workflow();
  assert.ok(
    ids.every((id) => pending.points[id].shortlisted),
    'All three queue advances precede server persistence',
  );
  release();
  await page.getByText('Saving dismissal…', { exact: true }).waitFor({ state: 'hidden' });
  await page.unroute(api + '/workflow/*');
  const saved = await workflow();
  assert.ok(
    ids.every((id) => saved.points[id].dismissed && !saved.points[id].shortlisted),
    'Queued decisions save without losing a revision',
  );
  assert.deepEqual(coverage, []);
  tracking = false;
  await reloadExisting(page);
  await page.getByLabel('Run selector').selectOption('search-fixture');
  const nav = page.getByRole('navigation', { name: 'Scouting workflow' });
  await page.waitForFunction(
    () =>
      Array.from(document.querySelectorAll('.workflow-stages button')).find((b) =>
        b.textContent.includes('Approach'),
      )?.disabled,
  );
  assert.equal(await nav.getByRole('button', { name: /Inspect/ }).isDisabled(), true);

  // A failed dismissal of the final spot restores the queue and focus as well.
  await decide(ids[0], 'shortlist');
  await nav.getByRole('button', { name: /Approach/ }).click();
  await page.getByLabel('Focused approach spot').waitFor();
  tracking = true;
  let releaseFailure;
  const failureGate = new Promise((resolve) => {
    releaseFailure = resolve;
  });
  await page.route(api + '/workflow/' + ids[0], async (route) => {
    await failureGate;
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      json: { detail: 'Simulated final-spot save failure' },
    });
  });
  await page.getByRole('button', { name: 'Dismiss spot & next', exact: true }).click();
  await page
    .getByText('No spots remain on the shortlist.', { exact: false })
    .waitFor({ timeout: 1500 });
  releaseFailure();
  await page.getByText('Could not dismiss ' + ids[0] + '.', { exact: false }).waitFor();
  await page.waitForFunction(
    (id) => document.querySelector('[aria-label="Focused approach spot"]')?.value === id,
    ids[0],
  );
  assert.equal((await workflow()).points[ids[0]].shortlisted, true);
  await page.unroute(api + '/workflow/' + ids[0]);
  assert.deepEqual(coverage, []);
  await page.screenshot({ path: out + '/restored-final-spot.png', fullPage: true });
  for (const cid of ids) await decide(cid, 'restore');
  // Leaving Approach restores the user's coverage setting.
  tracking = false;
  await nav.getByRole('button', { name: /Find/ }).click();
  await page
    .locator('.coverage-status')
    .filter({ hasText: 'Coverage ready' })
    .waitFor({ timeout: 60000 });
  assert.ok(JSON.parse(await page.locator('.map').getAttribute('data-coverage-cache')).length > 0);
  assert.deepEqual(errors, []);
  fs.writeFileSync(out + '/results.json', JSON.stringify({ timings, coverage, errors }, null, 2));
  console.log(
    'Three immediate queued dismissals, final-spot persistence/reload/rollback and returning coverage verified',
    timings,
  );
} catch (e) {
  await page.screenshot({ path: out + '/failure.png', fullPage: true });
  fs.writeFileSync(out + '/failure.txt', await page.locator('body').innerText());
  throw e;
} finally {
  await browser.close();
}
