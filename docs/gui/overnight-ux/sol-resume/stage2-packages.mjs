// Real service error paths using deliberately unavailable packages in disposable state.
import { chromium } from "../../../../trail_scout/web/node_modules/playwright/index.mjs";
import fs from "node:fs";
import assert from "node:assert/strict";
const base = process.env.TRAILSCOUT_URL,
  core = process.env.TRAILSCOUT_MISSING_CORE_URL,
  out = process.env.TRAILSCOUT_SCREENSHOTS;
assert.ok(base && core && out);
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
const page = await browser.newPage({
    viewport: { width: 820, height: 900 },
    acceptDownloads: true,
  }),
  errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  const original = await (await page.request.get(base + "/api/draft")).json();
  const profiles = await (
    await page.request.get(base + "/api/profiles")
  ).json();
  // Configure a real unsupported timed objective, then verify its explicit off switch.
  await page.request.put(base + "/api/draft", {
    data: {
      settings: {
        ...(original.settings || {}),
        profile: { preset: "together", ...profiles.together },
        practical_plan: {
          version: 1,
          policy: { task: "identify", leaf: "unknown" },
          search_minutes_cap: null,
        },
      },
    },
  });
  await page.goto(base);
  await page.waitForFunction(
    () => !document.querySelector(".input-fields").disabled,
  );
  await page
    .getByText("Timed practical plans · experimental", { exact: true })
    .click();
  await page
    .getByText(
      "Installed community package required. Established planning remains available.",
      { exact: true },
    )
    .waitFor();
  const enabled = page.getByLabel("Use practical objective for AM/PM plans");
  assert.ok(await enabled.isChecked());
  assert.ok(await enabled.isEnabled());
  // A retained opt-in with genuinely unavailable data fails visibly, then retries with an explicit edit.
  const previous = await page.locator("main").getAttribute("data-analysis-id");
  await page
    .getByRole("button", {
      name: /^(Compare route opportunities|Recalculate comparison)/,
    })
    .click();
  await page
    .getByRole("button", { name: "Retry calculation", exact: true })
    .waitFor({ timeout: 120000 });
  await page.getByText(/Last calculation failed/).waitFor();
  await enabled.uncheck();
  assert.ok(await enabled.isDisabled());
  await page.screenshot({ path: out + "/01-missing-community.png" });
  await page
    .getByRole("button", { name: "Retry calculation", exact: true })
    .click();
  await page.waitForFunction(
    (old) => {
      const id = document.querySelector("main")?.dataset.analysisId;
      return id && id !== old;
    },
    previous,
    { timeout: 120000 },
  );
  await page.locator(".recommendation").waitFor({ timeout: 120000 });
  assert.ok(
    (await page.locator(".recommendation").innerText()).includes(
      "ESTABLISHED PLANNING",
    ),
  );
  await page.screenshot({
    path: out + "/02-established-fallback-explicit.png",
  });
  await page.goto(core);
  await page.getByText(/Core package unavailable/).waitFor();
  assert.ok(await page.locator(".compare").isDisabled());
  await page.locator(".saved-card button").first().click();
  await page.locator(".saved-exports").waitFor();
  assert.ok(
    (await page.locator(".notice").innerText()).includes(
      "earlier source/model revisions",
    ),
  );
  const download = page.waitForEvent("download");
  await page.locator('a[href$="/export/gpx"]').click();
  await (await download).saveAs(out + "/retained.gpx");
  assert.ok(fs.statSync(out + "/retained.gpx").size > 100);
  await page.screenshot({ path: out + "/03-missing-core-saved-export.png" });
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    out + "/evidence.json",
    JSON.stringify(
      {
        status: "passed",
        actualMissingCommunity: true,
        realFailedJobAndExplicitRetry: true,
        explicitEstablishedFallback: true,
        actualMissingCore: true,
        retainedSavedExport: true,
        errors,
      },
      null,
      2,
    ),
  );
  console.log("Actual missing-package browser checks passed");
} catch (e) {
  await page.screenshot({ path: out + "/failure.png" });
  fs.writeFileSync(
    out + "/failure.txt",
    await page.locator("body").innerText(),
  );
  throw e;
} finally {
  await browser.close();
}
