// Offline real-area map timings. Run through gui/performance.py browser.
import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base = process.env.HUNTMAPS_URL,
  out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out) throw Error('Use gui/performance.py browser with disposable state');
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
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  const errors = [],
    external = [],
    requests = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (r) => {
    if (r.url().startsWith('http') && !r.url().startsWith(base)) external.push(r.url());
    if (r.url().includes('/tiles/visible/')) requests.push(r.url());
  });
  await page.addInitScript(() => localStorage.setItem('huntmaps-online-imagery', 'off'));
  const ready = (id) =>
    page
      .locator('.coverage-status')
      .filter({ hasText: 'Coverage ready · ' + id })
      .waitFor({ timeout: 60000 });
  const start = performance.now();
  await page.goto(base);
  await page.getByLabel('Select A0075', { exact: true }).click();
  await ready('A0075');
  const firstMs = performance.now() - start;
  if (await page.locator('.setup-group summary').count())
    await page.locator('.setup-group summary').first().click();
  const switches = [];
  for (const id of ['V010', 'V008', 'A0075', 'V010', 'V008', 'A0075']) {
    const began = performance.now();
    await page.getByLabel('Select ' + id, { exact: true }).click();
    await ready(id);
    switches.push({ id, ms: performance.now() - began });
  }
  const cdp = await page.context().newCDPSession(page);
  const heap = await cdp.send('Runtime.getHeapUsage');
  await page.screenshot({ path: out + '/map-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 900, height: 900 });
  await ready('A0075');
  await page.screenshot({ path: out + '/map-900.png', fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  fs.writeFileSync(
    out + '/map-performance.json',
    JSON.stringify(
      { firstMs, switches, heap, errors, external, visibleRequests: requests.length },
      null,
      2,
    ),
  );
  console.log('Actual offline map load and switching measured:', out);
} finally {
  await browser.close();
}
