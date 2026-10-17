import { chromium } from 'playwright';
import { openExisting } from './browser-startup.mjs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const base = process.env.HUNTMAPS_URL,
  out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out || !process.env.HUNTMAPS_WORKSPACE)
  throw Error('Run through gui.check in isolated state');
fs.mkdirSync(out, { recursive: true });
const fixture = execFileSync(
  path.resolve('../../.venv/bin/python'),
  [
    '-c',
    `
import json, os, pathlib, sys
root=pathlib.Path(os.environ['HUNTMAPS_SOURCE_DIR'])
assert pathlib.Path(os.environ['HUNTMAPS_STATE_DIR']) != root/'.gui'
assert pathlib.Path(os.environ['HUNTMAPS_WORKSPACE']) != root
sys.path.insert(0,str(root/'tests'))
from test_gui_lidar_recovery import make_lidar_plan
from huntmaps_gui import first_person as fp, first_person_worker as worker
from huntmaps_gui.catalog import Run
from huntmaps_gui.storage import write
r=Run('search-fixture'); cid=next(iter(r.points))
worker.publish(r,cid,[])
plan=make_lidar_plan(r,cid)
bad=fp.new_plan(r.id,[cid],'best')
print(json.dumps(dict(run=r.id,cid=cid,plan=plan['id'],bad=bad)))
`,
  ],
  { encoding: 'utf8' },
);
const { run, cid, plan, bad } = JSON.parse(fixture.trim().split('\n').at(-1));
const url = base + '/api/runs/' + run + '/first-person/' + cid;
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
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  page.setDefaultTimeout(45000);
  const errors = [],
    evidence = {};
  page.on('pageerror', (e) => errors.push(e.message));
  await page.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
  await page.route('**/*', (r) =>
    r.request().url().startsWith(base) || r.request().url().startsWith('blob:')
      ? r.continue()
      : r.abort(),
  );
  let attempts = 0,
    failAt = 0;
  let failedPreparation;
  const fakeJob = () => ({
    id: (attempts === 1 ? 'f' : 'e').repeat(32),
    plan: attempts === 1 ? bad : plan,
    kind: 'first-person-plan',
    status: attempts === 1 ? (Date.now() < failAt ? 'running' : 'failed') : 'complete',
    started: 1,
    stage: 'Checking scene source metadata',
    elapsed_s: 1,
    logs: '',
    error: attempts === 1 && Date.now() >= failAt ? 'Injected catalog failure' : null,
  });
  await page.route('**/api/first-person/plans', async (route) => {
    assert.equal(route.request().postDataJSON().fidelity, 'best');
    attempts++;
    failAt = Date.now() + 800;
    await route.fulfill({ json: fakeJob() });
  });
  await page.route('**/api/jobs', async (route) => {
    const response = await route.fetch();
    const jobs = await response.json();
    await route.fulfill({
      json: attempts
        ? [...jobs, ...(failedPreparation ? [failedPreparation] : []), fakeJob()]
        : jobs,
    });
  });
  for (const id of ['f'.repeat(32), 'e'.repeat(32)])
    await page.route('**/api/jobs/' + id, (r) => r.fulfill({ json: fakeJob() }));
  await page.route('**/api/jobs/' + 'd'.repeat(32), (r) => r.fulfill({ json: failedPreparation }));
  await page.route('**/api/first-person/plans/' + plan + '/start', async (route) => {
    if (failedPreparation) return route.continue();
    failedPreparation = {
      id: 'd'.repeat(32),
      plan,
      kind: 'first-person-prepare',
      status: 'failed',
      started: 2,
      stage: 'Preparing fine ground',
      elapsed_s: 1,
      logs: '',
      error: 'Injected preparation failure',
    };
    await route.fulfill({ json: failedPreparation });
  });
  const before = await (await page.request.get(url)).json();
  assert.equal(before.fine_observer_available, false);
  await openExisting(page, base);
  await page.getByLabel('Run selector').selectOption(run);
  await page.getByLabel('Saved neighborhood').selectOption('all');
  await page.getByLabel('Select ' + cid, { exact: true }).click();
  await page.getByRole('button', { name: 'View', exact: true }).click();
  await page.getByText('Fine ground unavailable at this setup.', { exact: false }).waitFor();
  assert.equal(
    await page.getByRole('button', { name: 'Refine standing position', exact: true }).isDisabled(),
    true,
  );
  await page
    .getByRole('button', { name: 'Improve detail for standing position', exact: true })
    .click();
  await page
    .getByRole('button', { name: 'Checking available detail…', exact: true })
    .waitFor({ timeout: 200 });
  await page
    .getByText('Source check did not complete. Retry Improve detail.', { exact: false })
    .waitFor();
  let panel = await page.locator('.fp-preparation').innerText();
  assert.ok(!panel.includes('NaN') && !panel.includes('Checking catalog metadata'));
  assert.ok(!panel.includes('sec · cached'));
  assert.ok(panel.includes('Unavailable until source sizes are known'));
  assert.equal((await (await page.request.get(url)).json()).key, before.key);
  await page.setViewportSize({ width: 900, height: 900 });
  await page.screenshot({ path: out + '/lidar-failed-900.png', fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.getByRole('button', { name: 'Retry Improve detail', exact: true }).click();
  const prepare = page.getByRole('button', { name: 'Prepare views', exact: true });
  await prepare.waitFor();
  await page.waitForFunction(() =>
    [...document.querySelectorAll('button')].some(
      (b) => b.textContent === 'Prepare views' && !b.disabled,
    ),
  );
  await prepare.click();
  await page.getByRole('dialog', { name: 'First-person modeled view', exact: true }).getByText('Injected preparation failure', { exact: false }).first().waitFor();
  assert.equal(await page.locator('.fp-preparation').evaluate((el) => el.open), true);
  assert.equal((await (await page.request.get(url)).json()).key, before.key);
  await page.getByRole('button', { name: 'Retry preparation', exact: true }).click();
  await page.waitForFunction(() => {
    const s = JSON.parse(document.querySelector('.fp-scene')?.dataset.camera || '{}');
    return s.loaded && s.vegetationVisible && s.vegetationTriangles > 0;
  });
  const after = await (await page.request.get(url)).json();
  assert.notEqual(after.key, before.key);
  assert.equal(after.fine_observer_available, true);
  await page.getByText('Lidar-supported inferred vegetation available', { exact: false }).waitFor();
  assert.equal(await page.locator('.fp-preparation').evaluate((el) => el.open), false);
  assert.equal(
    await page.getByRole('button', { name: 'Refine standing position', exact: true }).isEnabled(),
    true,
  );
  await page.getByRole('button', { name: 'Refine standing position', exact: true }).click();
  await page.getByRole('button', { name: 'Move observer one foot north', exact: true }).click();
  await page.waitForFunction(
    () =>
      Math.abs(
        JSON.parse(document.querySelector('.fp-scene')?.dataset.camera || '{}').north_m - 0.3048,
      ) < 0.001,
  );
  const camera = async () =>
    JSON.parse(await page.locator('.fp-scene').getAttribute('data-camera'));
  for (const width of [1500, 900]) {
    await page.setViewportSize({ width, height: width === 900 ? 900 : 1050 });
    await page.getByLabel('First-person heading', { exact: true }).fill('0');
    await page.getByLabel('First-person look angle', { exact: true }).fill('0');
    const scene = page.locator('.fp-scene');
    await scene.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => {
      const s = JSON.parse(document.querySelector('.fp-scene').dataset.camera);
      return s.vegetationVisible && s.heading === 0 && s.look === 0;
    });
    const on = await scene.screenshot({ path: out + '/lidar-on-' + width + '.png' });
    await page
      .getByRole('dialog')
      .getByText('Sources, coverage and technical details', { exact: true })
      .click();
    await page.getByLabel('Inferred vegetation', { exact: true }).uncheck();
    await page.waitForFunction(
      () => !JSON.parse(document.querySelector('.fp-scene').dataset.camera).vegetationVisible,
    );
    await scene.scrollIntoViewIfNeeded();
    const off = await scene.screenshot({ path: out + '/lidar-off-' + width + '.png' });
    assert.notEqual(Buffer.compare(on, off), 0, 'Foliage must change rendered scene pixels');
    await page.getByLabel('Inferred vegetation', { exact: true }).check();
    await page
      .getByRole('dialog')
      .getByText('Sources, coverage and technical details', { exact: true })
      .click();
    evidence[width] = await camera();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  }
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    out + '/lidar-recovery.json',
    JSON.stringify({ run, cid, before: before.key, after: after.key, evidence, errors }, null, 2),
  );
  console.log(
    'Lidar recovery: failure/retry, real cached LAS preparation, visible foliage, direct scene replacement and standing-position refinement passed at desktop and 900 px',
  );
} finally {
  await browser.close();
}
