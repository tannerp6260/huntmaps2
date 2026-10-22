import { chromium } from "../../../../trail_scout/web/node_modules/playwright/index.mjs";
import fs from "node:fs";
import assert from "node:assert/strict";
const base = process.env.TRAILSCOUT_URL;
const out = process.env.TRAILSCOUT_SCREENSHOTS;
assert.ok(base && out);
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
  viewport: { width: 1366, height: 900 },
  acceptDownloads: true,
});
const page = await context.newPage(),
  errors = [],
  external = [],
  steps = [],
  positions = {};
page.on("pageerror", (e) => errors.push(e.message));
page.on("request", (r) => {
  if (r.url().startsWith("http") && !r.url().startsWith(base))
    external.push(r.url());
});
async function get(p) {
  const r = await page.request.get(base + "/api" + p);
  assert.equal(r.status(), 200, await r.text());
  return r.json();
}
async function capture(name) {
  await page.screenshot({ path: out + "/" + name + ".png", fullPage: true });
  fs.writeFileSync(
    out + "/" + name + ".txt",
    await page.locator("body").innerText(),
  );
}
async function position(name, loc) {
  positions[name] = await loc.evaluate((e) => {
    const r = e.getBoundingClientRect();
    return { x: r.x, y: r.y + scrollY, width: r.width, height: r.height };
  });
}
try {
  await page.goto(base);
  await page.getByText("Core ready", { exact: false }).waitFor();
  await page
    .getByLabel("Mapped entry / assumed parking")
    .locator("option")
    .nth(1)
    .waitFor({ state: "attached" });
  await capture("01-start-laptop");
  await position(
    "compare",
    page.getByRole("button", { name: "Compare route opportunities" }),
  );
  const entries = await get("/starts"),
    entry = entries.find((e) => e.label === "Flattop Bench · entry");
  assert.ok(entry);
  await page
    .getByLabel("Mapped entry / assumed parking")
    .selectOption(entry.id);
  steps.push("Select Flattop Bench entry");
  await page
    .getByText("Timed practical plans · experimental", { exact: true })
    .click();
  steps.push("Expand timed practical settings");
  await page.getByLabel("Use practical objective for AM/PM plans").check();
  steps.push("Opt into timed practical plans");
  const previousAnalysis = await page
    .locator("main")
    .getAttribute("data-analysis-id");
  const started = performance.now();
  await page
    .getByRole("button", {
      name: /^(Compare route opportunities|Recalculate comparison)/,
    })
    .click();
  steps.push("Compare");
  await page.waitForFunction(
    (previous) => {
      const id = document.querySelector("main")?.dataset.analysisId;
      return id && id !== previous;
    },
    previousAnalysis,
    { timeout: 120000 },
  );
  await page
    .getByRole("region", { name: "Timed practical plan" })
    .waitFor({ timeout: 120000 });
  const elapsed = performance.now() - started;
  const result = await get(
    "/analyses/" +
      (await page.locator("main").getAttribute("data-analysis-id")),
  );
  fs.writeFileSync(out + "/analysis.json", JSON.stringify(result, null, 2));
  await page.evaluate(() => scrollTo(0, 0));
  await capture("02-result-laptop");
  await page.screenshot({ path: out + "/02-result-viewport.png" });
  await position("recommendation", page.locator(".recommendation"));
  assert.equal(
    await page.locator(".map").getAttribute("data-option-id"),
    result.recommended.am,
  );
  assert.equal(
    await page.locator(".map").getAttribute("data-analysis-id"),
    result.analysis_id,
  );
  await position(
    "save",
    page.getByRole("button", { name: "Save this plan", exact: true }),
  );
  await page
    .getByText(/Foreground inspection ·/)
    .first()
    .click();
  steps.push("Open foreground inspection");
  await page
    .getByText(/No clear-opening certification/)
    .first()
    .waitFor();
  await capture("03-inspection");
  await page.getByRole("button", { name: "Schedule", exact: true }).click();
  steps.push("Open Schedule to read observation/return");
  await capture("04-schedule");
  await page
    .getByLabel("Plan name", { exact: true })
    .fill("Stage 2 matched task · Flattop AM");
  steps.push("Name plan");
  await page
    .getByRole("button", { name: "Save this plan", exact: true })
    .click();
  steps.push("Save");
  await page
    .getByRole("button", { name: "Save a new version", exact: true })
    .waitFor();
  const dl = page.waitForEvent("download");
  await page.locator('a[href$="/export/gpx"]').click();
  await (await dl).saveAs(out + "/baseline.gpx");
  steps.push("Export GPX");
  const panel = page.locator(".recommendation");
  const periods = [];
  for (const mode of ["pm", "am"]) {
    const begin = performance.now();
    await page.getByLabel("Plan period", { exact: true }).selectOption(mode);
    await page.waitForFunction(
      (m) => document.querySelector(".recommendation")?.dataset.mode === m,
      mode,
    );
    periods.push({ mode, uiMs: performance.now() - begin });
  }
  fs.writeFileSync(out + "/ui-latency.json", JSON.stringify(periods, null, 2));
  await page.setViewportSize({ width: 820, height: 900 });
  await page.evaluate(() => scrollTo(0, 0));
  await capture("05-narrow");
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  const selected = result.options.find((o) => o.id === result.recommended.am);
  fs.writeFileSync(
    out + "/evidence.json",
    JSON.stringify(
      {
        base,
        steps,
        positions,
        elapsedAnalysisUiMs: elapsed,
        errors,
        external,
        overflow,
        analysisId: result.analysis_id,
        settings: result.settings,
        recommended: result.recommended,
        options: result.options.map((o) => ({
          id: o.id,
          viewpoints: o.viewpoints.map((p) => ({
            id: p.id,
            longitude: p.longitude,
            latitude: p.latitude,
          })),
          movement: o.movement,
          remaining: o.remaining,
          schedules: o.schedules,
        })),
        selected,
        sourceRevision: result.source_revision,
        implementation: result.implementation,
      },
      null,
      2,
    ),
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  console.log(
    JSON.stringify({
      status: "passed",
      steps: steps.length,
      positions,
      elapsedAnalysisUiMs: elapsed,
      overflow,
      options: result.options.length,
      recommended: result.recommended,
    }),
  );
} catch (e) {
  await capture("failure");
  throw e;
} finally {
  await browser.close();
}
