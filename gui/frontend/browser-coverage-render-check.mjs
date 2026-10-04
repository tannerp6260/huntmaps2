import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const base = process.env.HUNTMAPS_URL,
  out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out) throw Error('Run through ./gui/check');
fs.mkdirSync(out, { recursive: true });
const python = fileURLToPath(new URL('../../.venv/bin/python', import.meta.url));
const png = (rgb) =>
  Buffer.from(
    execFileSync(
      python,
      [
        '-c',
        `import base64,io; from PIL import Image; b=io.BytesIO(); Image.new('RGB',(256,256),${rgb}).save(b,format='PNG'); print(base64.b64encode(b.getvalue()).decode())`,
      ],
      { encoding: 'utf8' },
    ).trim(),
    'base64',
  );
const online = png('(70,100,70)'),
  saved = png('(110,90,65)');
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
const evidence = [],
  errors = [];
let page;
try {
  page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  await page.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'on'));
  page.on('pageerror', (e) => errors.push(e.message));
  // Opaque imagery fixtures expose occlusion. Real coverage comes from the local tile API.
  // Routing disables HTTP caching; the independent cache journey intentionally has no routing.
  await page.route('**/*', async (route) => {
    const url = route.request().url();
    if (url.startsWith('https://basemap.nationalmap.gov/'))
      return route.fulfill({ status: 200, contentType: 'image/png', body: online });
    if (url.startsWith(base) && url.includes('/tiles/imagery/'))
      return route.fulfill({ status: 200, contentType: 'image/png', body: saved });
    if (url === base + '/api/runs/search-fixture') {
      const response = await route.fetch(),
        run = await response.json();
      run.imagery = [
        { path: 'opaque-render-test.png', acquisition_date: 'synthetic test fixture' },
      ];
      return route.fulfill({ response, json: run });
    }
    return url.startsWith(base) || url.startsWith('blob:') ? route.continue() : route.abort();
  });
  await page.goto(base);
  await page.getByLabel('Run selector').selectOption('search-fixture');
  const run = await (await page.request.get(base + '/api/runs/search-fixture')).json();
  const [a, b] = run.recommendation_ids;
  const ready = (id) =>
    page
      .locator('.coverage-status')
      .filter({ hasText: 'Coverage ready · ' + id })
      .waitFor({ timeout: 60000 });
  const pixels = async (label, expectBlue = true, waitForIdle = true) => {
    if (waitForIdle) await page.waitForFunction(
      () => JSON.parse(document.querySelector('.map').dataset.mapState || '{}').loaded,
    );
    // Wait through a paint after the Ready label; inspect canvas pixels, not the label.
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    );
    const path = out + '/' + label + '.png';
    await page.locator('.maplibregl-canvas').screenshot({ path });
    const count = Number(
      execFileSync(
        python,
        [
          '-c',
          "import sys; import numpy as np; from PIL import Image; a=np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype('int16'); print(((a[:,:,2]>a[:,:,0]+40)&(a[:,:,1]>a[:,:,0]+35)&(a[:,:,2]>105)).sum())",
          path,
        ],
        { encoding: 'utf8' },
      ),
    );
    evidence.push({ label, cyanPixels: count });
    if (expectBlue)
      assert.ok(
        count > 1000,
        `${label}: loaded coverage must produce visible blue pixels (got ${count})`,
      );
    else assert.ok(count < 1000, `${label}: opacity zero must hide coverage (got ${count})`);
    return count;
  };
  await ready(a);
  await pixels('01-online-and-saved');
  // A movement event used to zero opacity even for already loaded tiles.
  const canvas = page.locator('.maplibregl-canvas'), rect = await canvas.boundingBox();
  await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2);
  await page.mouse.down(); await page.mouse.move(rect.x + rect.width / 2 + 30, rect.y + rect.height / 2, { steps: 5 });
  await pixels('01b-during-pan', true, false); await page.mouse.up();
  await ready(a);

  await page.getByText('Map layers', { exact: true }).click();
  const cached = page.getByLabel('Cached aerial imagery', { exact: true }),
    network = page.getByLabel('Online imagery — fill gaps', { exact: true });
  await cached.uncheck();
  await ready(a);
  await pixels('02-online-only');
  await page.getByLabel('Select ' + b, { exact: true }).click();
  await ready(b);
  await pixels('03-switched-online');
  await page.getByLabel('Select ' + a, { exact: true }).click();
  await ready(a);
  await pixels('04-returned-online');
  await page.getByLabel('Overlay opacity').fill('0.7');
  await ready(a);
  await pixels('05-opacity-update');
  await network.uncheck();
  await ready(a);
  await pixels('06-offline');
  await network.check();
  await ready(a);
  await pixels('07-online-reenabled');
  await cached.check();
  await ready(a);
  await pixels('08-saved-reenabled');
  await page.getByLabel('Overlay opacity').fill('0');
  await ready(a);
  await pixels('09-explicitly-hidden', false);
  await page.getByLabel('Overlay opacity').fill('0.5');
  await ready(a);
  await pixels('10-visible-again');
  await page.getByLabel('Compare ' + a, { exact: true }).check();
  await page.getByLabel('Compare ' + b, { exact: true }).check();
  await page.locator('.coverage-status').filter({ hasText: 'Coverage ready' }).waitFor();
  await pixels('11-comparison');
  await page.getByRole('button', { name: 'Exit compare', exact: true }).click();
  await ready(a);
  await pixels('12-exit-comparison');
  await page.screenshot({ path: out + '/render-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 900, height: 900 });
  await ready(a);
  await pixels('13-render-900');
  await page.screenshot({ path: out + '/render-900.png', fullPage: true });
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    out + '/results.json',
    JSON.stringify(
      {
        evidence,
        errors,
        imagery: 'opaque local PNG fixtures',
        coverage: 'actual saved viewshed tile API',
      },
      null,
      2,
    ),
  );
  console.log(
    'Visible coverage pixels above opaque online/saved imagery, reuse, opacity, toggles and comparison verified:',
    out,
  );
} catch (error) {
  if (page) {
    await page.screenshot({ path: out + '/failure.png', fullPage: true });
    fs.writeFileSync(out + '/failure.txt', await page.locator('body').innerText());
  }
  throw error;
} finally {
  await page?.unrouteAll({ behavior: 'wait' });
  await browser.close();
}
