// Actual GMU54 service, disposable state only. No analytical response fixtures.
import { chromium } from "../../../../trail_scout/web/node_modules/playwright/index.mjs";
import fs from "node:fs";
import assert from "node:assert/strict";
const base = process.env.TRAILSCOUT_URL;
const out = process.env.TRAILSCOUT_SCREENSHOTS;
assert.ok(base && out, "Supply disposable service URL and evidence directory");
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
  images = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("request", (r) => {
  if (r.url().startsWith("http") && !r.url().startsWith(base))
    external.push(r.url());
  if (r.url().includes(".png")) images.push(r.url());
});
const facts = {};
async function get(path) {
  const response = await page.request.get(base + "/api" + path);
  assert.equal(response.status(), 200, await response.text());
  return response.json();
}
async function capture(name) {
  await page.screenshot({ path: `${out}/${name}.png` });
  fs.writeFileSync(
    `${out}/${name}.txt`,
    await page.locator("body").innerText(),
  );
}
function clock(value) {
  return new Date(value).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Denver",
    timeZoneName: "short",
  });
}
async function checkSelection(result, id, mode) {
  const panel = page.locator(".recommendation"),
    option = result.options.find((o) => o.id === id);
  await page.waitForFunction(
    ({ id, mode }) => {
      const node = document.querySelector(".recommendation");
      return node?.dataset.optionId === id && node?.dataset.mode === mode;
    },
    { id, mode },
  );
  const selectedIndex = await page
    .locator(".option")
    .evaluateAll((nodes) =>
      nodes.findIndex((n) => n.classList.contains("selected")),
    );
  assert.equal(result.options[selectedIndex].id, id);
  assert.equal(
    await page.getByLabel("Time variant", { exact: true }).inputValue(),
    mode,
  );
  const schedule = option.schedules[mode],
    movement = schedule.movement || option.movement;
  assert.ok(
    (await panel.innerText()).includes(
      (movement.distance_m / 1609.344).toFixed(2) + " mi",
    ),
  );
  if (schedule.feasible) {
    const minutes = schedule.events
      .filter((e) => e.kind === "observe")
      .reduce((s, e) => s + e.minutes, 0);
    assert.ok((await panel.innerText()).includes(Math.round(minutes) + " min"));
    assert.ok(
      (await panel.innerText()).includes(
        clock(
          schedule.events.filter((e) => e.kind === "return").at(-1).arrival,
        ),
      ),
    );
  }
  if (schedule.practical) {
    await page.waitForFunction(
      (n) => Number(document.querySelector(".map").dataset.scanSectors) === n,
      schedule.practical.sectors.features.length,
    );
    await page.waitForFunction(
      (url) =>
        performance
          .getEntriesByType("resource")
          .some((r) => r.name.endsWith(url)),
      schedule.practical.coverage_url,
    );
    assert.ok(
      (
        await page
          .getByRole("region", { name: "Timed practical plan" })
          .innerText()
      ).includes(option.viewpoints[0].latitude.toFixed(6)),
    );
  }
}
try {
  await page.goto(base);
  await page.getByText("Core ready", { exact: false }).waitFor();
  await page.getByLabel("Who is going?").selectOption("together");
  const entry = (await get("/starts")).find(
    (e) => e.label === "Flattop Bench · entry",
  );
  await page
    .getByLabel("Mapped entry / assumed parking")
    .selectOption(entry.id);
  await page
    .getByText("Timed practical plans · experimental", { exact: true })
    .click();
  await page.getByLabel("Use practical objective for AM/PM plans").check();
  const previousAnalysis = await page
    .locator("main")
    .getAttribute("data-analysis-id");
  const begin = performance.now();
  await page
    .getByRole("button", {
      name: /^(Compare route opportunities|Recalculate comparison)/,
    })
    .click();
  await page.waitForFunction(
    (previous) => {
      const id = document.querySelector("main")?.dataset.analysisId;
      return id && id !== previous;
    },
    previousAnalysis,
    { timeout: 120000 },
  );
  await page.locator(".recommendation").waitFor();
  facts.elapsedAnalysisUiMs = performance.now() - begin;
  const result = await get(
    "/analyses/" +
      (await page.locator("main").getAttribute("data-analysis-id")),
  );
  facts.analysisId = result.analysis_id;
  facts.recommended = result.recommended;
  facts.settings = result.settings;
  assert.deepEqual(result.recommended, {
    am: "8865d096a44376b7094c6a3822cf9f07",
    pm: "9779d39be307bf56030cce6be738ad7a",
  });
  await checkSelection(result, result.recommended.am, "am");
  await page.evaluate(() => scrollTo(0, 0));
  facts.panelPosition = await page.locator(".recommendation").boundingBox();
  await capture("01-result-laptop");
  await page.getByLabel("Plan period", { exact: true }).selectOption("pm");
  await checkSelection(result, result.recommended.pm, "pm");
  await page
    .getByRole("button", { name: "Review schedule", exact: true })
    .click();
  await page.waitForFunction(
    () =>
      document.activeElement?.getAttribute("aria-label") ===
      "Selected schedule",
  );
  assert.equal(
    await page
      .getByRole("region", { name: "Selected schedule" })
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await page
    .getByText("Fits conservative arrival, observation and return checks")
    .waitFor();
  await capture("02-schedule-focus");
  await page.getByLabel("Plan period", { exact: true }).selectOption("am");
  await page.getByText("Compare a different option", { exact: true }).click();
  const alternative = page
    .locator(".recommendation-alternatives button")
    .first();
  await alternative.click();
  const altId = await page
    .locator(".recommendation")
    .getAttribute("data-option-id");
  assert.notEqual(altId, result.recommended.am);
  await checkSelection(result, altId, "am");
  await page
    .getByRole("button", { name: "Back to recommendation", exact: true })
    .click();
  await page.getByText("Compare a different option", { exact: true }).click();
  await page
    .getByRole("button", { name: "Inspect route & sightlines", exact: true })
    .click();
  await page
    .getByText(/Foreground inspection ·/)
    .first()
    .click();
  await page
    .getByText(/No clear-opening certification/)
    .first()
    .waitFor();
  await capture("03-sightline-inspection");
  await page
    .getByRole("button", { name: "Name, save & export", exact: true })
    .click();
  assert.equal(
    await page
      .getByLabel("Plan name", { exact: true })
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await page
    .getByLabel("Plan name", { exact: true })
    .fill("Sol stage1 · Flattop AM");
  await page
    .getByRole("button", { name: "Save this plan", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save a new version", exact: true })
    .waitFor();
  const saved = await get("/plans/" + (await get("/plans"))[0].id);
  assert.equal(saved.option.id, result.recommended.am);
  assert.equal(saved.mode, "am");
  const downloading = page.waitForEvent("download");
  await page.locator('a[href$="/export/gpx"]').click();
  await (await downloading).saveAs(out + "/selected.gpx");
  facts.savedId = saved.id;
  facts.selectedCoordinates = saved.option.viewpoints.map((p) => [
    p.longitude,
    p.latitude,
  ]);
  await page.getByLabel("Daily miles limit", { exact: true }).fill("2.25");
  await page
    .locator(".recommendation-warning")
    .getByText(/Previous calculation/)
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Save a new version", exact: true })
      .isDisabled(),
    true,
  );
  facts.layouts = [];
  for (const width of [1366, 820, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator(".recommendation").scrollIntoViewIfNeeded();
    if (width > 700) await page.evaluate(() => scrollTo(0, 0));
    const actual = await page.evaluate(() => ({
      width: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    assert.equal(actual.width, actual.scrollWidth);
    facts.layouts.push(actual);
    await capture(`04-stale-${width}`);
  }
  // Native select and jump links remain usable from the keyboard.
  await page.getByLabel("Plan period", { exact: true }).focus();
  await page.keyboard.press("Tab");
  assert.equal(
    await page
      .getByRole("button", { name: "Inspect route & sightlines", exact: true })
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () =>
      document.activeElement?.getAttribute("aria-label") ===
      "Selected route inspection",
  );
  assert.equal(
    await page
      .getByRole("region", { name: "Selected route inspection" })
      .evaluate((e) => e === document.activeElement),
    true,
  );
  const previousJobs = new Set((await get("/jobs")).map((j) => j.id));
  await page.getByRole("button", { name: /^Recalculate comparison/ }).click();
  await page
    .getByText(
      "Calculation in progress. This is the previous preview; wait for the new result before saving.",
      { exact: true },
    )
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Save a new version", exact: true })
      .isDisabled(),
    true,
  );
  const running = (await get("/jobs")).find((j) => !previousJobs.has(j.id));
  assert.ok(running);
  await page
    .getByRole("button", { name: "Cancel calculation", exact: true })
    .click();
  const deadline = Date.now() + 120000;
  let cancelled;
  while (Date.now() < deadline) {
    cancelled = await get("/jobs/" + running.id);
    if (!["pending", "running", "cancelling"].includes(cancelled.status)) break;
    await page.waitForTimeout(100);
  }
  assert.equal(cancelled.status, "cancelled");
  await page
    .getByText(
      "Calculation in progress. This is the previous preview; wait for the new result before saving.",
      { exact: true },
    )
    .waitFor({ state: "hidden" });
  await page
    .locator(".recommendation-warning")
    .getByText(/Previous calculation/)
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Save a new version", exact: true })
      .isDisabled(),
    true,
  );
  facts.cancelledJob = { id: running.id, status: cancelled.status };
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  facts.errors = errors;
  facts.external = external;
  facts.coverageImagesRequested = images;
  fs.writeFileSync(out + "/evidence.json", JSON.stringify(facts, null, 2));
  console.log(
    JSON.stringify({
      status: "passed",
      ...facts,
      settings: undefined,
      coverageImagesRequested: undefined,
    }),
  );
} catch (error) {
  await capture("failure");
  throw error;
} finally {
  await browser.close();
}
