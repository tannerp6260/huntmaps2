import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

// Release fixtures may write state or stop their own worker. Verify the runner's
// full disposable layout, including real paths, before allowing either action.
export function assertIsolatedReleaseState(env = process.env) {
  assert.ok(env.HUNTMAPS_STATE_DIR && env.HUNTMAPS_WORKSPACE, 'Use ./gui/check isolated state');
  const temporaryRoot = path.resolve(env.TMPDIR || '/tmp');
  assert.ok(temporaryRoot === '/tmp' || temporaryRoot.startsWith('/tmp/huntmaps-ux-sol-'), 'Unrecognized disposable test root');
  const state = path.resolve(env.HUNTMAPS_STATE_DIR);
  const work = path.dirname(state);
  assert.equal(path.basename(state), 'state');
  assert.match(path.basename(work), /^huntmaps-check-[a-zA-Z0-9_-]+$/);
  assert.equal(path.dirname(work), temporaryRoot);
  assert.equal(fs.realpathSync(state), state, 'Disposable state must not be a symlink');
  assert.equal(path.resolve(env.HUNTMAPS_WORKSPACE), path.join(work, 'workspace'));
  assert.equal(fs.realpathSync(env.HUNTMAPS_WORKSPACE), path.join(work, 'workspace'));
  return state;
}
