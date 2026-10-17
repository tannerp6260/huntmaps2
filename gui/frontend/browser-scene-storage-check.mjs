import { openExisting, reloadExisting } from './browser-startup.mjs';
import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const base = process.env.HUNTMAPS_URL,
  out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out) throw Error('Use an isolated GUI test server');
fs.mkdirSync(out, { recursive: true });
const runId = process.env.HUNTMAPS_SCENE_TEST_RUN || 'workflow-fixture';
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
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.route('**/*', (route) =>
  route.request().url().startsWith(base) || route.request().url().startsWith('blob:')
    ? route.continue()
    : route.abort(),
);
const headers = { 'X-HuntMaps': 'local' };
try {
  const run = await (await page.request.get(base + '/api/runs/' + runId)).json();
  const cid = process.env.HUNTMAPS_SCENE_TEST_POINT || run.candidates[0].id;
  const response = await page.request.post(base + '/api/first-person/plans', {
    headers,
    data: { run_id: runId, ids: [cid], fidelity: 'terrain' },
  });
  assert.equal(response.status(), 200, await response.text());
  const job = await response.json(),
    planId = job.plan;
  for (let n = 0; n < 100; n++) {
    const jobs = await (await page.request.get(base + '/api/jobs')).json();
    const j = jobs.find((j) => j.plan === planId);
    if (j?.status === 'complete') break;
    if (j?.status === 'failed') throw Error(j.error);
    if (n === 99) throw Error('Scene source-plan timeout');
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const planUrl = base + '/api/first-person/plans/' + planId;
  const plan = await (await page.request.get(planUrl)).json();
  assert.equal(plan.estimated_new_bytes, 0);
  assert.equal(plan.storage.blocked, false);
  assert.equal(plan.storage.scene_assets.estimated_output_bytes, 60000000);
  await page.addInitScript(
    ({ runId, planId }) => {
      localStorage.setItem('huntmaps-online-imagery', 'off');
      localStorage.setItem('huntmaps-first-person-plan:' + runId, planId);
    },
    { runId, planId },
  );
  async function viewer() {
    await page.getByLabel('Run selector').selectOption(runId);
    await page.getByLabel('Saved neighborhood').selectOption('all');
    await page.getByLabel('Select ' + cid, { exact: true }).click();
    await page.getByRole('button', { name: 'View', exact: true }).click();
    const section = page.locator('.fp-preparation');
    if ((await section.getAttribute('open')) === null)
      await section.locator('summary').first().click();
    await section.getByText('Saved scenes:', { exact: false }).waitFor();
    return section;
  }
  await openExisting(page, base);
  let section = await viewer();
  assert.equal(
    await section.getByRole('button', { name: 'Prepare views', exact: true }).isDisabled(),
    false,
  );
  assert.ok((await section.innerText()).includes('retained partial scenes:'));
  assert.ok((await section.innerText()).includes('keep 20 GiB free'));
  await page.screenshot({ path: out + '/storage-review.png', fullPage: true });
  await section.getByRole('button', { name: 'Prepare views', exact: true }).click();
  await page.waitForFunction(
    async (id) => {
      const jobs = await (await fetch('/api/jobs')).json();
      return jobs.some(
        (j) => j.plan === id && j.kind === 'first-person-prepare' && j.status === 'complete',
      );
    },
    planId,
    { timeout: 60000 },
  );
  const meta = await (
    await page.request.get(base + '/api/runs/' + runId + '/first-person/' + cid)
  ).json();
  assert.equal(meta.status, 'ready');
  // A low-space review must disable Prepare before submitting any job.
  await page.route(planUrl, async (route) => {
    const response = await route.fetch();
    const value = await response.json();
    value.storage.blocked = true;
    value.storage.volumes.forEach((v) => {
      v.free_bytes = value.storage.reserve_bytes + value.storage.required_bytes - 1;
    });
    await route.fulfill({ response, json: value });
  });
  await reloadExisting(page);
  section = await viewer();
  await section.getByText('Insufficient storage for this plan', { exact: false }).waitFor();
  assert.equal(
    await section.getByRole('button', { name: 'Prepare views', exact: true }).isDisabled(),
    true,
  );
  await page.setViewportSize({ width: 900, height: 900 });
  await page.screenshot({ path: out + '/storage-blocked-900.png', fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    out + '/results.json',
    JSON.stringify({ plan, ready: meta.key, errors }, null, 2),
  );
  console.log('Scene storage usage, terrain-only preparation and low-space UI verified', out);
} catch (e) {
  await page.screenshot({ path: out + '/failure.png', fullPage: true });
  fs.writeFileSync(out + '/failure.txt', await page.locator('body').innerText());
  throw e;
} finally {
  await browser.close();
}
