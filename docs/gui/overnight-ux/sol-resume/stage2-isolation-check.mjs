import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
// Applied only after the initial full GUI run finishes; preserve its failure evidence.
import { assertIsolatedReleaseState } from "../../../../gui/frontend/browser-isolation.mjs";
const root = "/tmp/huntmaps-ux-sol-stage2/isolation";
fs.mkdirSync(root, { recursive: true });
const work = fs.mkdtempSync(path.join(root, "huntmaps-check-"));
fs.mkdirSync(path.join(work, "state"));
fs.mkdirSync(path.join(work, "workspace"));
const env = {
  TMPDIR: root,
  HUNTMAPS_STATE_DIR: path.join(work, "state"),
  HUNTMAPS_WORKSPACE: path.join(work, "workspace"),
};
assert.equal(assertIsolatedReleaseState(env), env.HUNTMAPS_STATE_DIR);
const invalid = [
  {},
  { ...env, TMPDIR: "/tmp/unrecognized-root" },
  { ...env, HUNTMAPS_STATE_DIR: "/tmp/huntmaps-ux-sol-stage2/owner/state" },
  { ...env, HUNTMAPS_STATE_DIR: path.join(work, "other") },
  { ...env, HUNTMAPS_WORKSPACE: path.join(work, "other") },
  { ...env, TMPDIR: "/tmp" },
];
for (const e of invalid) assert.throws(() => assertIsolatedReleaseState(e));
const alias = fs.mkdtempSync(path.join(root, "huntmaps-check-alias-"));
fs.symlinkSync(path.join(work, "state"), path.join(alias, "state"));
fs.symlinkSync(path.join(work, "workspace"), path.join(alias, "workspace"));
assert.throws(() =>
  assertIsolatedReleaseState({
    ...env,
    HUNTMAPS_STATE_DIR: path.join(alias, "state"),
    HUNTMAPS_WORKSPACE: path.join(alias, "workspace"),
  }),
);
console.log(
  "Scoped release state accepted; seven missing/wrong-root/layout/workspace/symlink cases rejected",
);
