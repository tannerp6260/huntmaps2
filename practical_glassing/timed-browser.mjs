// Real service and installed sources. No analytical response mocks.
import { chromium } from "../gui/frontend/node_modules/playwright/index.mjs";
import assert from "node:assert/strict";
import fs from "node:fs";
const base = process.env.TRAILSCOUT_URL,
  out = process.env.TRAILSCOUT_SCREENSHOTS;
if (!base || !out) throw Error("Run through TrailScout gate");
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
  viewport: { width: 1450, height: 1000 },
  acceptDownloads: true,
});
const page = await context.newPage(),
  errors = [],
  probes = [],
  external = [];
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
async function compare(editDuring = false) {
  const old = new Set((await get("/jobs")).map((j) => j.id));
  await page
    .getByRole("button", {
      name: /^(Compare route opportunities|Recalculate comparison)/,
    })
    .click();
  let job;
  for (let i = 0; i < 100; i++) {
    job = (await get("/jobs")).find(
      (j) => !old.has(j.id) && j.kind !== "prepare",
    );
    if (job) break;
    await page.waitForTimeout(100);
  }
  assert.ok(job);
  if (editDuring)
    await page
      .getByLabel("Timed search task", { exact: true })
      .selectOption("spot");
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const t = performance.now();
    job = await get("/jobs/" + job.id);
    probes.push(performance.now() - t);
    if (job.status === "completed") break;
    assert.ok(
      !["failed", "cancelled", "interrupted"].includes(job.status),
      JSON.stringify(job),
    );
    await page.waitForTimeout(100);
  }
  assert.equal(job.status, "completed");
  const r = await get("/analyses/" + job.analysis_id);
  await page.waitForFunction(
    (id) => document.querySelector("main")?.dataset.analysisId === id,
    r.analysis_id,
  );
  return r;
}
try {
  await page.goto(base);
  await page.getByText("Core ready", { exact: false }).waitFor();
  const entries = await get("/starts");
  const entry = entries.find((e) => e.label === "Flattop Bench · entry");
  assert.ok(entry);
  // Restore a small clean UI config, keeping real service inputs and normal controls.
  await page.request.put(base + "/api/draft", {
    data: {
      settings: {
        date: "2026-10-31",
        profile: { preset: "together" },
        vehicle: "truck",
        start_id: entry.id,
        candidate_budget: 32,
        corridor_m: 2500,
        view_radius_m: 1500,
        search_envelope_m: 300,
        excluded_segments: [],
        excluded_areas: [],
        rejected: [],
        pinned: [],
        restrictions: [],
        schedule: {},
        explore_unknown: false,
        travel_area: null,
        target_area: null,
      },
    },
  });
  await page.reload();
  await page
    .getByText("Timed practical plans · experimental", { exact: true })
    .click();
  await page.getByLabel("Use practical objective for AM/PM plans").check();
  await page.getByLabel("Timed scan cap", { exact: true }).fill("");
  let r = await compare(true);
  assert.equal(r.settings.practical_plan.policy.task, "identify");
  assert.equal(
    await page.getByLabel("Timed search task", { exact: true }).inputValue(),
    "spot",
  );
  assert.equal(
    await page
      .getByRole("button", { name: /^Save (this plan|a new version)$/ })
      .isDisabled(),
    true,
  );
  r = await compare();
  assert.equal(r.settings.practical_plan.policy.task, "spot");
  assert.equal(r.search.pair_search_leaders, r.search.supported_viewpoints);
  await page.getByRole("region", { name: "Timed practical plan" }).waitFor();
  await page.getByRole("button", { name: "Marginal", exact: true }).click();
  await page
    .getByText("Practical relative-index m²", { exact: true })
    .waitFor();
  await page.getByLabel("Time variant", { exact: true }).selectOption("pm");
  let option = r.options.find((o) => o.id === r.recommended.pm);
  assert.ok(option);
  await page.waitForFunction(
    (n) =>
      Number(
        document.querySelector("[data-scan-sectors]")?.dataset.scanSectors,
      ) === n,
    option.schedules.pm.practical.sectors.features.length,
  );
  assert.equal(await page.locator(".option.selected .recommended").count(), 1);
  await page
    .getByText(/Foreground inspection ·/)
    .first()
    .click();
  await page
    .getByText(/No clear-opening certification/)
    .first()
    .waitFor();
  await page.screenshot({
    path: out + "/timed-flattop-pm.png",
    fullPage: true,
  });
  await page
    .getByLabel("Plan name", { exact: true })
    .fill("Timed practical real Flattop PM");
  await page
    .getByRole("button", { name: /^Save (this plan|a new version)$/ })
    .click();
  await page
    .getByRole("button", { name: "Save a new version", exact: true })
    .waitFor();
  const plans = await get("/plans");
  const saved = await get("/plans/" + plans[0].id);
  assert.equal(saved.mode, "pm");
  assert.equal(saved.version, 2);
  assert.deepEqual(
    saved.option.schedules.pm.practical,
    option.schedules.pm.practical,
  );
  for (const kind of ["json", "md", "geojson", "gpx"]) {
    const promise = page.waitForEvent("download");
    await page.locator(`a[href$="/export/${kind}"]`).click();
    await (await promise).saveAs(out + "/timed-plan." + kind);
  }
  const geo = JSON.parse(fs.readFileSync(out + "/timed-plan.geojson", "utf8"));
  assert.deepEqual(
    geo.features.filter((f) => f.properties.kind === "selected scan footprint"),
    option.schedules.pm.practical.sectors.features,
  );
  assert.match(fs.readFileSync(out + "/timed-plan.gpx", "utf8"), /<trkseg>/);
  await page.reload();
  await page.getByRole("region", { name: "Timed practical plan" }).waitFor();
  await page
    .getByText("Timed practical plans · experimental", { exact: true })
    .click();
  await page.getByLabel("Timed scan cap", { exact: true }).fill("30");
  await page
    .getByLabel("Timed leaf assumption", { exact: true })
    .selectOption("off");
  await page.getByLabel("Outing date", { exact: true }).fill("2026-11-01");
  r = await compare();
  assert.equal(r.settings.date, "2026-11-01");
  assert.equal(r.settings.practical_plan.search_minutes_cap, 30);
  assert.ok(
    r.options.every((o) =>
      Object.values(o.schedules).every(
        (s) =>
          !s.practical || s.practical.visits.every((v) => v.minutes_used <= 30),
      ),
    ),
  );
  await page.setViewportSize({ width: 900, height: 1000 });
  await page.screenshot({ path: out + "/timed-900.png", fullPage: true });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  probes.sort((a, b) => a - b);
  fs.writeFileSync(
    out + "/evidence.json",
    JSON.stringify(
      {
        analysis: r.analysis_id,
        source: r.source_revision,
        package: r.practical_plan.package,
        probes: probes.length,
        p95_ms: probes[Math.floor(probes.length * 0.95)],
        maximum_ms: Math.max(...probes),
        errors,
        external,
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
