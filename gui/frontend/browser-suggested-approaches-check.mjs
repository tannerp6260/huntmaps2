import { chromium } from 'playwright';
import { openExisting, reloadExisting } from './browser-startup.mjs';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const base = process.env.HUNTMAPS_URL, out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out || !process.env.HUNTMAPS_WORKSPACE) throw Error('Use gui.check');
fs.mkdirSync(out, { recursive: true });
const raw = execFileSync(path.resolve('../../.venv/bin/python'), ['-m', 'gui.suggested_fixture'],
  { cwd: process.env.HUNTMAPS_WORKSPACE, encoding: 'utf8' });
const f = JSON.parse(raw.trim().split('\n').at(-1));
const browser = await chromium.launch({ executablePath: process.env.HUNTMAPS_BROWSER || '/usr/bin/google-chrome',
  headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
page.setDefaultTimeout(60000);
const errors = [], submissions = [];
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => {
  if (r.method() === 'POST' && r.url() === `${base}/api/runs/${f.run}/approaches`) submissions.push(r.postDataJSON());
});
await page.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
await page.route('**/*', r => r.request().url().startsWith(base) || /^(blob:|data:)/.test(r.request().url()) ? r.continue() : r.abort());
const state = async () => (await page.request.get(`${base}/api/runs/${f.run}/workflow`)).json();
try {
  await openExisting(page, base);
  await page.getByLabel('Run selector').selectOption(f.run);
  await page.getByRole('button', { name: 'Plan approaches (2 shortlisted)', exact: true }).click();
  await page.getByRole('button', { name: 'Continue to inspect', exact: true }).waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent === 'Continue to inspect' && !b.disabled));
  const selected = await state();
  assert.equal(submissions.length, 2, 'One automatic calculation per shortlisted setup');
  assert.ok(submissions.every(s => s.mode === 'suggested' && s.ids.length === 1));
  for (const cid of f.ids) {
    const choice = selected.points[cid].approach;
    assert.ok(choice, 'Default path selected without comparison clicks');
    const s = await (await page.request.get(`${base}/api/approaches/${choice.scenario}`)).json();
    assert.equal(s.scenario.mode, 'suggested');
    assert.equal(s.results.results[0].alternatives.length, 1);
    assert.deepEqual(s.results.results[0].alternatives[0].offtrail.at(-1), [selected.points[cid].point.longitude, selected.points[cid].point.latitude]);
  }
  assert.equal(await page.getByRole('button', { name: 'Confirm approach search boundary', exact: true }).count(), 0);
  await page.screenshot({ path: out + '/suggested-paths-desktop.png', fullPage: true });
  await reloadExisting(page);
  await page.getByLabel('Run selector').selectOption(f.run);
  await page.getByRole('button', { name: /Approach.*selected/ }).click();
  await page.getByRole('button', { name: 'Explore alternatives or edit approach', exact: true }).waitFor();
  await page.waitForTimeout(700);
  assert.equal(submissions.length, 2, 'Reload reuses selected paths');
  await page.setViewportSize({ width: 900, height: 950 });
  await page.screenshot({ path: out + '/suggested-paths-900.png', fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  const focused = await page.getByLabel('Focused approach spot').inputValue();
  await page.getByRole('button', { name: 'Explore alternatives or edit approach', exact: true }).click();
  await page.locator('.approach-boundary-check[data-ready="true"]').waitFor();
  const submitted = page.waitForResponse(r => r.request().method() === 'POST' && r.url() === `${base}/api/runs/${f.run}/approaches`);
  await page.getByRole('button', { name: 'Recalculate approaches for ' + focused, exact: true }).click();
  const submission = await submitted;
  assert.equal(submission.status(), 200, await submission.text());
  const calculation = await submission.json();
  for (let i=0;i<240;i++) {
    const job=await(await page.request.get(`${base}/api/jobs/${calculation.job.id}`)).json();
    if(job.status==='complete')break;
    assert.equal(job.status,'running',JSON.stringify(job));
    await page.waitForTimeout(250);
  }
  await page.getByRole('button', { name: 'Use this approach & next spot', exact: true }).first().waitFor();
  assert.equal(submissions.length, 3);
  assert.equal(submissions[2].mode, 'alternatives');
  assert.equal((await state()).points[focused].approach, null, 'Alternative overrides require an explicit choice');
  await page.getByRole('button', { name: 'Use this approach & next spot', exact: true }).first().click();
  await page.getByRole('button', { name: /Open prepared view|Inspect current setup/ }).waitFor();
  assert.ok((await state()).points[focused].approach);
  await page.getByRole('button', { name: /Approach.*selected/ }).click();
  await page.getByLabel('Focused approach spot').selectOption(focused);
  await page.getByRole('button', { name: 'Use suggested approach mode', exact: true }).click();
  await page.getByRole('button', { name: 'Explore alternatives or edit approach', exact: true }).waitFor();
  for (let i = 0; i < 100; i++) {
    const review = await (await page.request.get(`${base}/api/runs/${f.run}/approach-review`)).json();
    if (review.drafts[focused]?.mode === 'suggested') break;
    assert.ok(i < 99, 'Suggested mode persisted before reload');
    await page.waitForTimeout(100);
  }
  await reloadExisting(page);
  await page.getByLabel('Run selector').selectOption(f.run);
  await page.getByRole('button', { name: /Approach.*selected/ }).click();
  await page.getByLabel('Focused approach spot').selectOption(focused);
  await page.getByRole('button', { name: 'Explore alternatives or edit approach', exact: true }).waitFor();
  assert.equal(submissions.length, 3, 'Switching back to suggestions retains the chosen override');
  assert.ok((await state()).points[focused].approach);
  assert.deepEqual(errors, []);
  fs.writeFileSync(out + '/results.json', JSON.stringify({ run: f.run, ids: f.ids, submissions, errors }, null, 2));
} catch (error) {
  await page.screenshot({ path: out + '/failure.png', fullPage: true });
  fs.writeFileSync(out + '/failure.txt', await page.locator('body').innerText());
  throw error;
} finally { await browser.close(); }
