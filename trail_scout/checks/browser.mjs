// Real GMU54 data and real local services. No API result is fabricated.
import { chromium } from "../web/node_modules/playwright/index.mjs";
import assert from "node:assert/strict";
import fs from "node:fs";

if (!process.env.TRAILSCOUT_URL || !process.env.TRAILSCOUT_SCREENSHOTS)
  throw Error(
    "Run ./trailscout check for an isolated actual-service browser gate",
  );
const base = process.env.TRAILSCOUT_URL,
  out = process.env.TRAILSCOUT_SCREENSHOTS;
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.TRAILSCOUT_BROWSER || "/usr/bin/google-chrome",
  headless: true,
  args: [
    "--no-sandbox",
    "--enable-unsafe-swiftshader",
    "--use-gl=angle",
    "--use-angle=swiftshader",
  ],
});
const context = await browser.newContext({
  viewport: { width: 1500, height: 1050 },
  acceptDownloads: true,
});
const page = await context.newPage();
const errors = [],
  external = [],
  probes = [],
  runs = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("request", (r) => {
  if (r.url().startsWith("http") && !r.url().startsWith(base))
    external.push(r.url());
});
async function get(path) {
  const r = await page.request.get(base + "/api" + path);
  assert.equal(r.status(), 200, await r.text());
  return r.json();
}
async function waitJob(id) {
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const started = performance.now();
    const j = await get("/jobs/" + id);
    probes.push(performance.now() - started);
    if (j.status === "completed") return j;
    if (["failed", "cancelled", "interrupted"].includes(j.status))
      throw Error(JSON.stringify(j));
    await page.waitForTimeout(150);
  }
  throw Error("Actual worker timeout");
}
async function compare() {
  const old = new Set((await get("/jobs")).map((j) => j.id));
  await page
    .getByRole("button", {
      name: /^(Compare route opportunities|Recalculate comparison)/,
    })
    .click();
  let j;
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    j = (await get("/jobs")).find(
      (j) => !old.has(j.id) && j.kind !== "prepare",
    );
    if (j) break;
    await page.waitForTimeout(50);
  }
  assert.ok(j, "A real analytical job was started");
  j = await waitJob(j.id);
  const r = await get("/analyses/" + j.analysis_id);
  runs.push({
    job: j,
    result: {
      analysis_id: r.analysis_id,
      start: r.start,
      search: r.search,
      grid: r.grid,
      performance: r.performance,
      options: r.options.map((o) => ({
        id: o.id,
        movement: o.movement,
        coverage: o.coverage,
      })),
    },
  });
  await page.waitForFunction(
    (id) => document.querySelector("main")?.dataset.analysisId === id,
    r.analysis_id,
  );
  await page.locator(".option").first().waitFor();
  await page.waitForTimeout(300);
  return r;
}
async function layout(width, name) {
  await page.setViewportSize({ width, height: 1050 });
  await page.waitForTimeout(700);
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await page.screenshot({ path: out + "/" + name + ".png", fullPage: true });
}
try {
  await page.goto(base);
  await page
    .getByLabel("Mapped entry / assumed parking")
    .locator("option")
    .nth(1)
    .waitFor({ state: "attached" });
  await page
    .getByRole("button", { name: "Compare route opportunities" })
    .waitFor();
  assert.ok((await get("/areas"))[0].diagnostics.dem.unknown_cells === 0);
  await page.getByLabel("Daily miles limit", { exact: true }).fill("3.25");
  await layout(1500, "01-prepared-overview");
  let first = await compare();
  assert.match(first.start.label, /Soap Creek/);
  assert.ok(first.options.length > 0);
  assert.ok(
    first.candidates.some((p) => p.kind === "off-trail spur" && p.feasible),
  );
  assert.ok(
    first.options.every(
      (o) =>
        o.movement.distance_m >=
        o.legs[0].distance_m + o.legs.at(-1).distance_m - 1e-5,
    ),
  );
  await page.getByRole("button", { name: "Coverage", exact: true }).click();
  await page.getByText("Unique coverage, counted once").waitFor();
  await page.getByRole("button", { name: "Access", exact: true }).click();
  await page.getByText("Competing access evidence").waitFor();
  await page.getByRole("button", { name: "Marginal", exact: true }).click();
  await page.getByText("When does more walking add little?").waitFor();
  await page.getByRole("button", { name: "Route", exact: true }).click();
  const profile = page.getByLabel("Linked route elevation profile");
  await profile.hover({ position: { x: 120, y: 60 } });
  await page.waitForTimeout(200);
  await page.getByText(/ft elevation · raw/).waitFor();
  await layout(1500, "02-real-soap-route");
  await layout(900, "03-real-soap-900");
  await page.getByRole("button", { name: "Schedule", exact: true }).click();
  await page.getByLabel("Time variant", { exact: true }).selectOption("pm");
  await page
    .getByText("Fits conservative arrival, observation and return checks")
    .waitFor();
  await layout(900, "04-evening-schedule");
  await page
    .getByLabel("Time variant", { exact: true })
    .selectOption("combined");
  await page.getByText("This time variant is not feasible").waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Save this plan", exact: true })
      .isDisabled(),
    true,
  );
  await page.getByLabel("Time variant", { exact: true }).selectOption("am");
  await page
    .getByLabel("Plan name", { exact: true })
    .fill("Real GMU54 Soap Creek · morning");
  await page
    .getByRole("button", { name: "Save this plan", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save a new version", exact: true })
    .waitFor();
  const old = (await get("/plans"))[0];
  const original = await get("/plans/" + old.id);
  assert.equal(original.settings.profile.max_miles, 3.25);
  for (const kind of ["md", "json", "gpx", "geojson"]) {
    const download = page.waitForEvent("download");
    await page.locator(`a[href$="/export/${kind}"]`).click();
    const file = await download;
    await file.saveAs(out + "/soap-plan." + kind);
  }
  await page.getByLabel("Time variant", { exact: true }).selectOption("pm");
  await page
    .getByLabel("Plan name", { exact: true })
    .fill("Real GMU54 Soap Creek · evening");
  await page
    .getByRole("button", { name: "Save a new version", exact: true })
    .click();
  await page.waitForFunction(
    () => document.querySelectorAll(".saved-card").length === 2,
  );
  let versions = await get("/plans");
  assert.equal(versions.length, 2);
  assert.equal(versions[0].parent_id, old.id);
  assert.deepEqual(await get("/plans/" + old.id), original);
  await page.reload();
  await page.locator(".saved-card").first().waitFor();
  await page
    .locator(".saved-card")
    .filter({ hasText: "Real GMU54 Soap Creek · morning" })
    .locator("button")
    .first()
    .click();
  await page.waitForFunction(
    () =>
      document.querySelector(".save-box input")?.value ===
      "Real GMU54 Soap Creek · morning",
  );
  await page.waitForTimeout(300);
  assert.equal(
    await page.getByLabel("Plan name", { exact: true }).inputValue(),
    "Real GMU54 Soap Creek · morning",
  );
  // Another real corridor using the same hunter and source assumptions.
  const entries = await get("/starts");
  const mill = entries.find((e) => e.label === "Flattop Bench · entry");
  assert.ok(mill);
  await page.getByLabel("Mapped entry / assumed parking").selectOption(mill.id);
  const second = await compare();
  assert.match(second.start.label, /Flattop Bench/);
  assert.ok(
    second.options.length,
    "Second real corridor has feasible evaluated plans",
  );
  assert.notEqual(second.start.id, first.start.id);
  await page
    .getByLabel("Plan name", { exact: true })
    .fill("Real GMU54 Flattop Bench comparison");
  const pmIndex = second.options.findIndex(
    (o) => o.id === second.recommended.pm,
  );
  assert.ok(
    pmIndex >= 0,
    "A supported evening variant exists in this real corridor",
  );
  await page.locator(".option").nth(pmIndex).click();
  // A comparison at a different entry is deliberately saved as a new version of
  // the selected outing, retaining the original immutable source and route.
  await page.getByLabel("Time variant", { exact: true }).selectOption("pm");
  if (
    await page
      .getByRole("button", { name: "Save a new version", exact: true })
      .isEnabled()
  ) {
    // Reopen latest parent to avoid overwriting another tab/version, then the
    // API independently enforces parent revision. This UI currently has the old
    // parent selected, so its first save should expose that conflict.
    await page
      .getByRole("button", { name: "Save a new version", exact: true })
      .click();
    await page.getByRole("alert").waitFor();
    assert.match(
      await page.getByRole("alert").innerText(),
      /Another saved version/,
    );
    await page.getByRole("button", { name: "Dismiss error" }).click();
  }
  await page
    .getByRole("button", { name: "Save as a separate plan", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save this plan", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save a new version", exact: true })
    .waitFor();
  assert.equal((await get("/plans")).length, 3);
  await layout(1500, "05-real-flattop-bench");
  // Pin an actual newly found viewpoint through the browser, then recalculate.
  await page.getByRole("button", { name: "Route", exact: true }).click();
  await page.locator(".viewpoint button").first().click();
  await page
    .getByRole("button", { name: "Pin this viewpoint", exact: true })
    .click();
  assert.equal(
    await page
      .getByRole("button", { name: "Save a new version", exact: true })
      .isDisabled(),
    true,
  );
  const pinned = await compare();
  assert.ok(pinned.settings.pinned.length === 1);
  assert.ok(pinned.options.every((o) => o.viewpoints.some((v) => v.pinned)));
  await page.locator(".viewpoint button").first().click();
  await page
    .getByRole("button", { name: "Reject this viewpoint", exact: true })
    .click();
  const rejected = await compare();
  assert.ok(rejected.settings.rejected.length === 1);
  assert.ok(
    rejected.options.every((o) =>
      o.viewpoints.every((v) => !rejected.settings.rejected.includes(v.id)),
    ),
  );
  // Cancel a real calculation and retain all saved versions. No fake worker.
  await page
    .getByText("Effort, optics & search limits", { exact: true })
    .click();
  await page
    .getByLabel("Viewpoint evaluation budget", { exact: true })
    .fill("33");
  await page.getByRole("button", { name: "Recalculate comparison" }).click();
  await page
    .getByRole("button", { name: "Cancel calculation", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Cancel calculation", exact: true })
    .click();
  const cancelDeadline = Date.now() + 30000;
  let cancelled;
  while (Date.now() < cancelDeadline) {
    cancelled = (await get("/jobs"))[0];
    if (cancelled.status === "cancelled") break;
    await page.waitForTimeout(100);
  }
  assert.equal(cancelled.status, "cancelled");
  assert.deepEqual(await get("/plans/" + old.id), original);
  await page
    .getByLabel("Viewpoint evaluation budget", { exact: true })
    .fill("32");
  await compare();
  // Preserve a newer pace edit across a deliberately delayed ACTUAL job reply.
  let release, seen, forwarded;
  const delivered = new Promise((r) => (forwarded = r));
  const submitted = new Promise((r) => (seen = r));
  const hold = new Promise((r) => (release = r));
  await page.route(base + "/api/jobs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    seen();
    await hold;
    await route.fulfill({ response });
    forwarded();
  });
  await page
    .getByRole("button", { name: "Compare route opportunities" })
    .click();
  await submitted;
  await page.getByLabel("Flat pace · mph", { exact: true }).fill("1.35");
  release();
  await delivered;
  await page.unroute(base + "/api/jobs");
  const staleJob = (await get("/jobs"))[0];
  await waitJob(staleJob.id);
  await page.waitForTimeout(1200);
  assert.equal(
    await page.getByLabel("Flat pace · mph", { exact: true }).inputValue(),
    "1.35",
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Save a new version", exact: true })
      .isDisabled(),
    true,
  );
  await page.getByText("INPUTS CHANGED", { exact: true }).waitFor();
  await compare();
  // Blocking every external resource leaves prepared data and exports usable.
  await context.route("https://**/*", (route) => route.abort());
  await page.reload();
  await page.locator(".saved-card").first().waitFor();
  assert.deepEqual(await get("/plans/" + old.id), original);
  // An unavailable local basemap is scoped to the map; saved work remains usable.
  await page.route("**/api/overview/**", (route) => route.abort());
  await page.route("**/artifacts/**/relief.png", (route) => route.abort());
  await page.reload();
  await page.locator(".saved-card").first().waitFor();
  await page.locator(".map-error").waitFor();
  const summary = await page.request.get(
    base + "/api/plans/" + old.id + "/export/md",
  );
  assert.equal(summary.status(), 200);
  assert.match(await summary.text(), /America\/Denver/);
  await page.unroute("**/api/overview/**");
  await page.unroute("**/artifacts/**/relief.png");
  await page.reload();
  await page.locator(".option").first().waitFor();
  await layout(900, "06-recovered-offline-900");
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  assert.ok(
    Math.max(...probes) < 3000,
    "Actual job/status HTTP remains responsive during analysis",
  );
  fs.writeFileSync(
    out + "/results.json",
    JSON.stringify(
      {
        errors,
        external,
        maximumStatusMs: Math.max(...probes),
        statusProbes: probes,
        runs,
        versions: await get("/plans"),
        cancelled,
      },
      null,
      2,
    ),
  );
  console.log("Actual-service browser journey passed:", out);
} catch (error) {
  await page.screenshot({ path: out + "/failure.png", fullPage: true });
  fs.writeFileSync(
    out + "/failure.txt",
    await page.locator("body").innerText(),
  );
  fs.writeFileSync(
    out + "/errors.json",
    JSON.stringify({ errors, external }, null, 2),
  );
  throw error;
} finally {
  await browser.close();
}
