import { chromium } from 'playwright';
import { openExisting, reloadExisting } from './browser-startup.mjs';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const base = process.env.HUNTMAPS_URL,
  out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out || !process.env.HUNTMAPS_WORKSPACE) throw Error('Use gui.check');
fs.mkdirSync(out, { recursive: true });
const raw = execFileSync(
  path.resolve('../../.venv/bin/python'),
  ['-m', 'gui.connectivity_fixture'],
  { cwd: process.env.HUNTMAPS_WORKSPACE, encoding: 'utf8' },
);
const f = JSON.parse(raw.trim().split('\n').at(-1));
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
let page, pausedPid;
try {
  page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  const errors = [], submissions = [];
  page.setDefaultTimeout(45000);
  page.on('pageerror', (e) => errors.push(e.message));
  await page.addInitScript((f) => {
    localStorage.setItem('huntmaps-last-area', f.run);
    localStorage.setItem('huntmaps-online-imagery', 'off');
  }, f);
  await page.route('**/*', (r) =>
    r.request().url().startsWith(base) || r.request().url().startsWith('blob:')
      ? r.continue()
      : r.abort(),
  );
  const endpoint = base + '/api/runs/' + f.run + '/connectivity-screen';
  // Hold only the first real disposable worker until Cancel reaches the server.
  // A fast worker can otherwise finish between rendering and clicking Cancel.
  let firstSubmission = true, cancelledJob;
  await page.route(endpoint, async (r) => {
    if (r.request().method() !== 'POST') return r.continue();
    await new Promise(resolve => setTimeout(resolve, 700));
    const response = await r.fetch();
    if (firstSubmission) {
      firstSubmission = false;
      assert.equal(response.status(), 200, await response.text());
      const value = await response.json();
      assert.equal(value.job.kind, 'connectivity-screen');
      assert.equal(value.job.name, f.run);
      assert.ok(process.env.HUNTMAPS_STATE_DIR?.startsWith('/tmp/huntmaps-check-'));
      const command = fs.readFileSync('/proc/' + value.job.pid + '/cmdline', 'utf8').split('\0');
      assert.ok(command.includes('huntmaps_gui.connectivity_worker') && command.includes(f.run));
      process.kill(-value.job.pid, 'SIGSTOP');
      pausedPid = value.job.pid;
      cancelledJob = value.job.id;
    }
    await r.fulfill({response});
  });
  await page.route(base + '/api/jobs/*/cancel', async route => {
    const response = await route.fetch();
    if (pausedPid) {
      process.kill(-pausedPid, 'SIGCONT');
      pausedPid = undefined;
    }
    await route.fulfill({response});
  });
  await openExisting(page, base, { screenConnections: true });
  const section = page.getByRole('region', { name: 'Terrain connection screen' });
  await page.getByLabel('Show all setups', { exact: true }).waitFor();
  assert.equal(await page.getByLabel('Show all setups', { exact: true }).isChecked(), false);
  await section.getByRole('button', { name: 'Cancel connection check', exact: true }).click();
  await section.getByRole('button', { name: 'Check connections', exact: true }).waitFor();
  const cancelled = await (await page.request.get(base + '/api/jobs/' + cancelledJob)).json();
  assert.equal(cancelled.status, 'cancelled', 'The real paused worker must be cancelled');
  await page.waitForFunction(() => {
    const b = [...document.querySelectorAll('.connection-screen button')].find(
      (b) => b.textContent === 'Check connections',
    );
    return b && !b.disabled;
  });
  await section.getByRole('button', { name: 'Check connections', exact: true }).click();
  await section.getByText('Starting connection check…', { exact: true }).waitFor({ timeout: 200 });
  let screen;
  for (let i = 0; i < 100; i++) {
    screen = await (await page.request.get(endpoint)).json();
    if (screen.status === 'complete') break;
    await page.waitForTimeout(200);
  }
  assert.equal(screen.status, 'complete');
  // Legacy history entries lacked name; recover using the retained screen token.
  const history = await (await page.request.get(base + '/api/jobs')).json();
  const originalJob = history.find(j => j.kind === 'connectivity-screen' && j.plan === screen.id);
  assert.ok(originalJob);
  const legacy = {...originalJob, name:null, status:'failed', stage:'Controlled connection recovery'};
  const recoveryList = route => route.fulfill({json:[legacy]});
  await page.evaluate(() => localStorage.setItem('huntmaps-connection-mode:workflow-fixture','all'));
  await page.getByLabel('Run selector').selectOption('workflow-fixture');
  await page.route('**/api/jobs', recoveryList);
  const wrongPlans=[];
  page.on('request', r => {if(r.url().includes('/api/plans/'+screen.id))wrongPlans.push(r.url());});
  await page.getByRole('button',{name:'Activity',exact:true}).click();
  await page.locator('details.jobs > summary').click();
  const recoveryJob=page.locator('.job').filter({hasText:'Controlled connection recovery'});
  const resume=recoveryJob.getByRole('button',{name:'Review / resume plan',exact:true});
  await resume.focus(); await page.keyboard.press('Enter');
  await page.waitForFunction(run => document.querySelector('[aria-label="Run selector"]').value === run, f.run);
  await section.waitFor();
  assert.deepEqual(wrongPlans,[],'Connection recovery never requests a baseline plan');
  await page.unroute('**/api/jobs',recoveryList);

  assert.equal(screen.points[f.found].status, 'connection_found');
  assert.equal(screen.points[f.blocked].status, 'no_connection');
  await page.getByLabel('Saved neighborhood').selectOption('all');
  await page.getByLabel('Select ' + f.found, { exact: true }).waitFor();
  assert.equal(await page.getByLabel('Select ' + f.blocked, { exact: true }).count(), 0);
  await page.getByLabel('Select ' + f.kept, { exact: true }).waitFor();
  await page.waitForFunction((f) => {
    const s = JSON.parse(document.querySelector('.map').dataset.mapState || '{}');
    return !s.candidateIds?.includes(f.blocked) && s.manualIds?.includes(f.manual);
  }, f);
  await page.getByLabel('Show all setups', { exact: true }).check();
  await page.getByLabel('Select ' + f.blocked, { exact: true }).waitFor();
  await page.getByLabel('Show all setups', { exact: true }).uncheck();
  await page.getByLabel('Recommendation mode').selectOption('complementary');
  await page.locator('.collection-suggestion').first().waitFor();
  const ids = await page.locator('.collection-suggestion b').allTextContents();
  assert.ok(!ids.includes(f.blocked));
  await page.getByLabel('Recommendation mode').selectOption('individual');
  await section.getByText('Connection settings', { exact: true }).click();
  const limit = page.getByLabel('Connection slope limit', { exact: true });
  await limit.fill('');
  await page.waitForTimeout(5200);
  assert.equal(await limit.inputValue(), '');
  assert.equal(
    await section.getByRole('button', { name: 'Apply connection limit', exact: true }).isDisabled(),
    true,
  );
  await limit.fill('36');
  assert.equal(
    await section.getByRole('button', { name: 'Apply connection limit', exact: true }).isDisabled(),
    true,
  );
  await limit.fill('25');
  // Missing coverage stays unknown; source preparation has one explicit approval.
  const missing = async (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({
          json: {
            ...screen,
            points: Object.fromEntries(
              Object.entries(screen.points).map(([id, p]) => [
                id,
                {
                  ...p,
                  status: 'unavailable',
                  reason: 'network_coverage',
                  message: 'Missing verified source coverage',
                },
              ]),
            ),
          },
        })
      : route.fallback();
  await page.route(endpoint, missing);
  await page.getByLabel('Show all setups', { exact: true }).check();
  await page.getByLabel('Show all setups', { exact: true }).uncheck();
  await section
    .getByRole('button', { name: 'Review roads/trails preparation', exact: true })
    .click();
  let approvals = 0;
  const failSource = async (route) => {
    assert.equal(route.request().postDataJSON().download, true);
    approvals++;
    await route.fulfill({ status: 503, json: { detail: 'Injected source preparation failure' } });
  };
  await page.route('**/api/network-plans/*/start', failSource);
  await section
    .getByRole('button', { name: 'Approve roads/trails preparation', exact: true })
    .click();
  await section
    .getByRole('alert')
    .filter({ hasText: 'Injected source preparation failure' })
    .waitFor();
  assert.equal(approvals, 1);
  await page.waitForTimeout(5200);
  await section
    .getByRole('alert')
    .filter({ hasText: 'Injected source preparation failure' })
    .waitFor();
  await page.unroute(endpoint, missing);
  await page.unroute('**/api/network-plans/*/start', failSource);
  await section.getByRole('button', { name: 'Check connections again', exact: true }).click();
  await page.getByLabel('Select ' + f.found, { exact: true }).waitFor();
  for (const width of [1500, 900]) {
    await page.setViewportSize({ width, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: out + '/connections-' + width + '.png', fullPage: true });
  }
  // A real synthetic 28-degree plane fails at 25 and succeeds after explicit retry at 30.
  await page.evaluate(
    (run) => localStorage.setItem('huntmaps-connection-mode:' + run, 'all'),
    f.retry_run,
  );
  let requested, completed;
  const staleRequested = new Promise((resolve) => (requested = resolve)),
    staleCompleted = new Promise((resolve) => (completed = resolve));
  let staleOnce = true;
  await page.route(endpoint, async (route) => {
    if (route.request().method() !== 'GET' || !staleOnce) return route.fallback();
    staleOnce = false;
    requested();
    await new Promise((resolve) => setTimeout(resolve, 900));
    await route.fulfill({ json: screen });
    completed();
  });
  await page.getByLabel('Show all setups', { exact: true }).check();
  await staleRequested;
  await page.getByLabel('Run selector').selectOption(f.retry_run);
  await page.waitForFunction(
    (run) => document.querySelector('.connection-screen')?.dataset.screenRun === run,
    f.retry_run,
  );
  await staleCompleted;
  assert.equal(await section.getAttribute('data-screen-run'), f.retry_run);
  await page.getByRole('button', { name: 'Plan approaches (1 shortlisted)', exact: true }).click();
  await page.getByRole('button', { name: 'Explore alternatives or edit approach', exact: true }).click();
  await page.getByText('A modeled connection appears at 30°.', { exact: true }).waitFor();
  assert.equal(
    (await (await page.request.get(base + '/api/approaches/' + f.scenario)).json()).scenario
      .maximum_slope_deg,
    25,
  );
  assert.equal(await page.getByLabel('Maximum approach slope').inputValue(), '25');
  await page.route('**/api/runs/' + f.retry_run + '/approaches', async (r) => {
    if (r.request().method() === 'POST') {
      submissions.push(r.request().postDataJSON());
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
    await r.continue();
  });
  await page.getByRole('button', { name: 'Recalculate at 30°', exact: true }).click();
  await page
    .getByRole('button', { name: 'Recalculating at 30°…', exact: true })
    .waitFor({ timeout: 200 });
  await page
    .getByRole('button', { name: 'Use this approach & next spot', exact: true })
    .first()
    .waitFor({ timeout: 60000 });
  assert.equal(submissions.length, 1);
  assert.equal(submissions[0].maximum_slope_deg, 30);
  const old = await (await page.request.get(base + '/api/approaches/' + f.scenario)).json();
  assert.equal(old.scenario.maximum_slope_deg, 25);
  assert.equal(old.results.results[0].alternatives.length, 0);
  await page.screenshot({ path: out + '/explicit-30-degree-retry.png', fullPage: true });
  assert.deepEqual(errors, []);
  fs.writeFileSync(out + '/results.json', JSON.stringify({ screen, submissions, errors }, null, 2));
  console.log(
    'Connections: exact screen worker, cancellation/retry, default filtering, Show all, manual/saved retention, complementary selection, numeric editing and explicit 25-to-30 retry verified at desktop and 900 px',
  );
} catch (error) {
  if (page) {
    await page.screenshot({path:out + '/failure.png',fullPage:true});
    fs.writeFileSync(out + '/failure.txt',await page.locator('body').innerText());
  }
  throw error;
} finally {
  if (pausedPid) {
    try { process.kill(-pausedPid, 'SIGCONT'); } catch (error) { if(error.code !== 'ESRCH') throw error; }
  }
  await browser.close();
}

