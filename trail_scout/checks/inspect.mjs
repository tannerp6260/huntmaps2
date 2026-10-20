import { chromium } from "../web/node_modules/playwright/index.mjs";
import fs from "node:fs";
const base = process.env.TRAILSCOUT_URL || "http://127.0.0.1:8767";
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
const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(base);
await page
  .getByRole("button", { name: "Compare route opportunities" })
  .waitFor({ state: "visible" });
await page.waitForTimeout(2000);
await page.screenshot({
  path: "/tmp/trailscout-initial-desktop.png",
  fullPage: true,
});
await page.getByRole("button", { name: "Compare route opportunities" }).click();
const start = Date.now();
let jobs = [];
while (Date.now() - start < 120000) {
  await page.waitForTimeout(500);
  jobs = await (await page.request.get(base + "/api/jobs")).json();
  if (jobs[0] && ["completed", "failed", "cancelled"].includes(jobs[0].status))
    break;
}
if (jobs[0]?.status !== "completed") throw Error(JSON.stringify(jobs[0]));
await page.locator(".option").first().waitFor();
await page.waitForTimeout(2000);
await page.screenshot({
  path: "/tmp/trailscout-first-desktop.png",
  fullPage: true,
});
await page.setViewportSize({ width: 900, height: 1000 });
await page.waitForTimeout(1000);
await page.screenshot({
  path: "/tmp/trailscout-first-900.png",
  fullPage: true,
});
fs.writeFileSync(
  "/tmp/trailscout-initial-browser.json",
  JSON.stringify({ errors, job: jobs[0] }, null, 2),
);
await browser.close();
if (errors.length) throw Error(JSON.stringify(errors));
