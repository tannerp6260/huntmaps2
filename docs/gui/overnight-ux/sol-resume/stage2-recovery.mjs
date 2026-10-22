// Real analytical results only. Transport delays/HTTP failures are explicitly injected.
import { chromium } from "../../../../trail_scout/web/node_modules/playwright/index.mjs";
import fs from "node:fs";
import assert from "node:assert/strict";
const base = process.env.TRAILSCOUT_URL,
  out = process.env.TRAILSCOUT_SCREENSHOTS;
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
  facts = {};
page.on("pageerror", (e) => errors.push(e.message));
async function get(path) {
  const r = await page.request.get(base + "/api" + path);
  assert.equal(r.status(), 200, await r.text());
  return r.json();
}
async function capture(name) {
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: false });
  fs.writeFileSync(
    `${out}/${name}.txt`,
    await page.locator("body").innerText(),
  );
}
async function compare() {
  const old = new Set((await get("/jobs")).map((j) => j.id));
  await page
    .getByRole("button", {
      name: /^(Compare route opportunities|Recalculate comparison)/,
    })
    .click();
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const j = (await get("/jobs")).find((j) => !old.has(j.id));
    if (j && ["failed", "cancelled"].includes(j.status)) throw Error(j.error);
    if (j?.status === "completed") {
      await page.waitForFunction(
        (id) => document.querySelector("main")?.dataset.analysisId === id,
        j.analysis_id,
      );
      return get("/analyses/" + j.analysis_id);
    }
    await page.waitForTimeout(100);
  }
  throw Error("Real analysis timed out");
}
function latch() {
  let release;
  const promise = new Promise((resolve) => (release = resolve));
  return { promise, release };
}
try {
  await page.goto(base);
  await page.getByLabel("Who is going?").waitFor();
  await page.waitForFunction(
    () => !document.querySelector(".input-fields").disabled,
  );
  const plans = await get("/plans"),
    saved = await get("/plans/" + plans[0].id);
  // A period-only navigation also invalidates a late open, even when no recommendation exists.
  const heldPeriod = latch(),
    periodArrived = latch();
  await page.route(`**/api/plans/${saved.id}`, async (route) => {
    const response = await route.fetch();
    periodArrived.release();
    await heldPeriod.promise;
    await route.fulfill({ response });
  });
  await page.locator(".saved-card button").first().click();
  await periodArrived.promise;
  await page.getByLabel("Plan period", { exact: true }).selectOption("pm");
  heldPeriod.release();
  await page.waitForTimeout(900);
  assert.equal(
    await page.getByLabel("Plan period", { exact: true }).inputValue(),
    "pm",
  );
  await page.unroute(`**/api/plans/${saved.id}`);
  facts.staleOpenPreservedPeriodOnly = true;
  // Late open-save responses must not overwrite newer effort edits.
  const heldOpen = latch(),
    openArrived = latch();
  await page.route(`**/api/plans/${saved.id}`, async (route) => {
    const response = await route.fetch();
    openArrived.release();
    await heldOpen.promise;
    await route.fulfill({ response });
  });
  await page.locator(".saved-card button").first().click();
  await openArrived.promise;
  await page.getByLabel("Daily miles limit", { exact: true }).fill("2.125");
  heldOpen.release();
  await page.waitForTimeout(900);
  assert.equal(
    await page.getByLabel("Daily miles limit", { exact: true }).inputValue(),
    "2.125",
  );
  await page.unroute(`**/api/plans/${saved.id}`);
  facts.staleOpenPreservedEdit = true;
  // Serialize PUTs: a delayed older draft must land before the newer one.
  const heldDraft = latch(),
    draftArrived = latch();
  let firstDraft = true;
  await page.route("**/api/draft", async (route) => {
    if (route.request().method() !== "PUT" || !firstDraft)
      return route.continue();
    firstDraft = false;
    draftArrived.release();
    await heldDraft.promise;
    await route.continue();
  });
  await page.getByLabel("Daily miles limit", { exact: true }).fill("2.2");
  await draftArrived.promise;
  await page.getByLabel("Daily miles limit", { exact: true }).fill("2.3");
  await page.waitForTimeout(800);
  heldDraft.release();
  await page.waitForFunction(
    async () =>
      (await (await fetch("/api/draft")).json()).settings.profile.max_miles ===
      2.3,
  );
  await page.waitForTimeout(1000);
  facts.draftOrdering = (await get("/draft")).settings.profile.max_miles;
  assert.equal(
    facts.draftOrdering,
    2.3,
    "Newest draft wins after delayed older PUT settles",
  );
  await page.unroute("**/api/draft");
  // The saved version and exports remain available on core-package HTTP failure.
  await page.route("**/api/areas", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Deliberate core-package transport failure",
      }),
    }),
  );
  await page.reload();
  await page.getByText(/Core package unavailable/).waitFor();
  assert.ok(
    await page
      .getByRole("button", {
        name: /^(Compare route opportunities|Recalculate comparison)/,
      })
      .isDisabled(),
  );
  await page.locator(".saved-card button").first().click();
  await page.getByText(/Opened immutable|Saved version uses earlier/).waitFor();
  assert.equal(
    (
      await page.request.get(base + `/api/plans/${saved.id}/export/gpx`)
    ).status(),
    200,
  );
  await capture("01-missing-core-http");
  await page.unroute("**/api/areas");
  await page
    .getByRole("button", { name: "Retry local sources", exact: true })
    .click();
  await page.getByText("Core ready", { exact: false }).waitFor();
  // Delayed date context is ignored after a newer date is selected.
  const heldContext = latch(),
    contextArrived = latch();
  await page.route(
    "**/api/context?date=2026-11-01&vehicle=truck",
    async (route) => {
      const response = await route.fetch();
      contextArrived.release();
      await heldContext.promise;
      await route.fulfill({ response });
    },
  );
  await page.getByLabel("Outing date", { exact: true }).fill("2026-11-01");
  await contextArrived.promise;
  await page.getByLabel("Outing date", { exact: true }).fill("2026-11-02");
  await page.waitForFunction(
    () => !document.querySelector(".compare").disabled,
  );
  heldContext.release();
  await page.waitForTimeout(300);
  assert.equal(
    await page.getByLabel("Outing date", { exact: true }).inputValue(),
    "2026-11-02",
  );
  await page.unroute("**/api/context?date=2026-11-01&vehicle=truck");
  facts.staleContext = true;
  // Entry-evidence HTTP failures have a working retry without losing inputs.
  await page.route("**/api/context?**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Deliberate context transport failure" }),
    }),
  );
  await page.getByLabel("Outing date", { exact: true }).fill("2026-11-03");
  await page
    .getByRole("button", { name: "Retry entry evidence", exact: true })
    .waitFor();
  assert.ok(await page.locator(".compare").isDisabled());
  await page.unroute("**/api/context?**");
  await page
    .getByRole("button", { name: "Retry entry evidence", exact: true })
    .click();
  await page.waitForFunction(
    () => !document.querySelector(".compare").disabled,
  );
  assert.equal(
    await page.getByLabel("Daily miles limit", { exact: true }).inputValue(),
    "2.5",
  ); // explicitly reopened saved settings
  facts.contextRetry = true;
  // A real supported-access scenario and zero timed scan cap produce no recommendation.
  await page.getByLabel("Outing date", { exact: true }).fill("2026-10-31");
  const access = page.getByText("Access assumptions & owner edits", {
    exact: true,
  });
  await access.click();
  await page.getByLabel("Explore unknown foot access as a scenario").check();
  await page
    .getByText("Timed practical plans · experimental", { exact: true })
    .click();
  await page.getByLabel("Timed scan cap", { exact: true }).fill("0");
  const empty = await compare();
  assert.equal(empty.settings.explore_unknown, true);
  assert.equal(empty.settings.practical_plan.search_minutes_cap, 0);
  assert.equal(empty.recommended.am, undefined);
  await page.getByText(/No recommendation fits morning/).waitFor();
  assert.ok(
    (await page.locator("main").innerText()).includes(
      "UNKNOWN FOOT ACCESS SCENARIO",
    ),
  );
  assert.equal(
    await page.getByLabel("Daily miles limit", { exact: true }).inputValue(),
    "2.5",
  );
  await capture("02-real-empty-scenario");
  facts.empty = {
    id: empty.analysis_id,
    recommended: empty.recommended,
    profile: empty.settings.profile,
    unknownScenario: true,
  };
  // Exact profile changes persist; objective edits remain explicit and stale until recalculated.
  await page.getByLabel("Who is going?").selectOption("dad");
  await page.getByLabel("Daily miles limit", { exact: true }).fill("2.4");
  await page
    .getByLabel("Timed search task", { exact: true })
    .selectOption("assess");
  await page.reload();
  await page.waitForFunction(
    () => !document.querySelector(".input-fields").disabled,
  );
  assert.equal(await page.getByLabel("Who is going?").inputValue(), "dad");
  assert.equal(
    await page.getByLabel("Daily miles limit", { exact: true }).inputValue(),
    "2.4",
  );
  await page
    .getByText("Timed practical plans · experimental", { exact: true })
    .click();
  assert.equal(
    await page.getByLabel("Timed search task", { exact: true }).inputValue(),
    "assess",
  );
  facts.profileObjectiveReload = true;
  assert.deepEqual(errors, []);
  facts.errors = errors;
  fs.writeFileSync(out + "/evidence.json", JSON.stringify(facts, null, 2));
  console.log(JSON.stringify({ status: "passed", ...facts }));
} catch (e) {
  await capture("failure");
  throw e;
} finally {
  await browser.close();
}
