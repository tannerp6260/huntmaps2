// Actual local API and installed GMU sources. No fabricated analytical responses.
import { chromium } from "../gui/frontend/node_modules/playwright/index.mjs";
import assert from "node:assert/strict";
import fs from "node:fs";
const base = process.env.TRAILSCOUT_URL,
  out = process.env.TRAILSCOUT_SCREENSHOTS;
if (!base || !out) throw Error("Run through the isolated TrailScout gate");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
  args: [
    "--no-sandbox",
    "--enable-unsafe-swiftshader",
    "--use-gl=angle",
    "--use-angle=swiftshader",
  ],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  acceptDownloads: true,
});
const page = await context.newPage();
const errors = [],
  external = [],
  probes = [];
context.on("page", (p) => p.on("pageerror", (e) => errors.push(e.message)));
page.on("pageerror", (e) => errors.push(e.message));
context.on("request", (r) => {
  if (r.url().startsWith("http") && !r.url().startsWith(base))
    external.push(r.url());
});
async function get(path) {
  const r = await page.request.get(base + "/api" + path);
  assert.equal(r.status(), 200, await r.text());
  return r.json();
}
try {
  await page.goto(base);
  await page.getByText("Core ready", { exact: false }).waitFor();
  const area = (await get("/areas"))[0];
  assert.equal(area.practical.status, "ready");
  const entries = await get("/starts");
  const soap = entries.find((e) => e.label === "Soap Creek · entry");
  assert.ok(soap);
  // Exercise real UI controls, then submit those settings through the real endpoint.
  await page
    .getByText("Community & scan review · experimental", { exact: true })
    .click();
  await page.getByLabel("Add practical static comparison").check();
  await page
    .getByLabel("Search task", { exact: true })
    .selectOption("identify");
  await page
    .getByLabel("Useful scan budget · minutes per point", { exact: true })
    .fill("30");
  const body = {
    date: "2026-10-31",
    start_id: soap.id,
    candidate_budget: 16,
    practical: { task: "identify", leaf: "unknown", scan_minutes: 30 },
  };
  const response = await page.request.post(base + "/api/jobs", { data: body });
  assert.equal(response.status(), 200, await response.text());
  let job = await response.json();
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const t = performance.now();
    job = await get("/jobs/" + job.id);
    probes.push(performance.now() - t);
    if (job.status === "completed") break;
    if (["failed", "cancelled", "interrupted"].includes(job.status))
      throw Error(JSON.stringify(job));
    await page.waitForTimeout(100);
  }
  assert.equal(job.status, "completed");
  const result = await get("/analyses/" + job.analysis_id);
  assert.ok(result.practical.rows.length);
  await page.request.put(base + "/api/draft", {
    data: { settings: result.settings },
  });
  await page.reload();
  await page
    .getByRole("region", { name: "Practical static review" })
    .waitFor({ timeout: 20000 });
  const r = result.practical;
  assert.match(
    await page
      .getByRole("region", { name: "Practical static review" })
      .innerText(),
    /static/,
  );
  await page.screenshot({
    path: out + "/practical-desktop.png",
    fullPage: true,
  });
  const report = await context.newPage();
  report.on("pageerror", (e) => errors.push(e.message));
  await report.goto(base + r.report_url);
  await report.locator("#rows tr").first().waitFor();
  assert.equal(await report.locator("#rows tr").count(), r.rows.length);
  const id = await report
    .locator("#rows tr")
    .first()
    .locator("button")
    .textContent();
  assert.ok(id.endsWith(r.orders.combined[0]));
  for (const arm of Object.keys(r.orders)) {
    await report.locator("#arm").selectOption(arm);
    assert.ok(
      (
        await report.locator("#rows tr").first().locator("button").textContent()
      ).endsWith(r.orders[arm][0]),
    );
  }
  await report.locator("#arm").selectOption("combined");
  await report.locator("#rows tr").first().locator("button").click();
  await report.waitForFunction(
    () => document.querySelector("#map").naturalWidth > 0,
  );
  assert.match(await report.locator("#detail").innerText(), /Scan sectors/);
  assert.equal(await report.locator("#layer").inputValue(), "point");
  await report.screenshot({
    path: out + "/practical-report-desktop.png",
    fullPage: true,
  });
  const downloadPromise = report.waitForEvent("download");
  await report
    .getByText("Provisional static waypoints GPX", { exact: true })
    .click();
  const download = await downloadPromise;
  await download.saveAs(out + "/shortlist.gpx");
  assert.match(
    fs.readFileSync(out + "/shortlist.gpx", "utf8"),
    /Provisional static opportunity/,
  );
  await page.setViewportSize({ width: 900, height: 1000 });
  await page.screenshot({ path: out + "/practical-900.png", fullPage: true });
  await report.setViewportSize({ width: 900, height: 1000 });
  await report.screenshot({
    path: out + "/practical-report-900.png",
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  probes.sort((a, b) => a - b);
  fs.writeFileSync(
    out + "/evidence.json",
    JSON.stringify(
      {
        analysis_id: result.analysis_id,
        source: result.source_revision,
        package: r.package,
        probes: probes.length,
        p95_ms: probes[Math.floor(probes.length * 0.95)],
        maximum_ms: Math.max(...probes),
        rows: r.rows.length,
        orders: r.orders,
        errors,
        external,
      },
      null,
      2,
    ),
  );
  console.log("Actual practical browser passed", out);
} finally {
  await browser.close();
}
