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
  }),
  page = await context.newPage();
const facts = { layouts: [] };
try {
  await page.goto(base);
  await page.locator(".recommendation").waitFor();
  await page.waitForFunction(
    () =>
      !document.querySelector(".input-fields").disabled &&
      !document.querySelector(".compare").disabled,
  );
  await page.waitForTimeout(500);
  for (const width of [1366, 820, 683, 390]) {
    await page.setViewportSize({ width, height: width === 683 ? 450 : 900 });
    await page.evaluate(() => scrollTo(0, 0));
    const layout = await page.evaluate(() => ({
      width: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      compareY:
        document.querySelector(".compare").getBoundingClientRect().y + scrollY,
      compareHeight: document.querySelector(".compare").getBoundingClientRect()
        .height,
    }));
    assert.equal(layout.scrollWidth, width);
    facts.layouts.push(layout);
    await page.screenshot({ path: `${out}/inputs-${width}.png` });
    await page
      .locator(".recommendation")
      .evaluate((e) => e.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: `${out}/decision-${width}.png` });
  }
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.getByLabel("Plan period", { exact: true }).focus();
  await page.keyboard.press("Tab");
  assert.equal(
    await page.evaluate(() => document.activeElement.textContent),
    "Inspect route & sightlines",
  );
  const outline = await page.evaluate(
    () => getComputedStyle(document.activeElement).outlineWidth,
  );
  assert.equal(outline, "3px");
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () =>
      document.activeElement?.getAttribute("aria-label") ===
      "Selected route inspection",
  );
  await page.getByRole("button", { name: "Schedule", exact: true }).focus();
  await page.keyboard.press("Enter");
  assert.equal(
    await page
      .getByRole("button", { name: "Schedule", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  await page
    .getByRole("button", { name: "Name, save & export", exact: true })
    .click();
  assert.ok(
    await page
      .getByLabel("Plan name", { exact: true })
      .evaluate((e) => e === document.activeElement),
  );
  facts.keyboardFocus = true;
  // Contrast checks for the main text and secondary/micro text, using actual computed colors.
  const colors = await page.evaluate(() =>
    [".recommendation", ".recommendation-context", ".controls .micro"].map(
      (selector) => {
        const e = document.querySelector(selector);
        return {
          selector,
          foreground: getComputedStyle(e).color,
          background: getComputedStyle(
            e.closest(".recommendation") || e.closest(".controls"),
          ).backgroundColor,
        };
      },
    ),
  );
  const lum = (rgb) => {
    const c = rgb
      .match(/[\d.]+/g)
      .slice(0, 3)
      .map(Number)
      .map((n) => {
        n /= 255;
        return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
      });
    return c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722;
  };
  facts.contrast = colors.map((c) => {
    const a = lum(c.foreground),
      b = lum(c.background);
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    assert.ok(ratio >= 4.5, JSON.stringify(c));
    return { ...c, ratio };
  });
  fs.writeFileSync(out + "/evidence.json", JSON.stringify(facts, null, 2));
  console.log(JSON.stringify({ status: "passed", ...facts }));
} catch (e) {
  await page.screenshot({ path: out + "/failure.png" });
  throw e;
} finally {
  await browser.close();
}
