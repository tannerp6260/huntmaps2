// Existing-work journeys choose their entry explicitly, just as an owner does.
export async function chooseExisting(page) {
  await page.getByRole('dialog', { name: 'Welcome to HuntMaps2', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Open existing work', exact: true }).click();
}
export async function openExisting(page, url, { screenConnections = false } = {}) {
  // Existing journeys inspect their original saved pools. The connection journey
  // opts into the new default and verifies its separate eligibility overlay.
  if (!screenConnections) await page.addInitScript(() => localStorage.setItem('huntmaps-connection-mode', 'all'));
  await page.goto(url);
  await chooseExisting(page);
}
export async function reloadExisting(page) {
  await page.reload();
  await chooseExisting(page);
}
export async function openNetworks(page) {
  if (await page.locator('.layers').getAttribute('open') === null)
    await page.locator('.layers > summary').click();
  const controls = page.locator('.network-map-controls');
  if (await controls.getAttribute('open') === null)
    await controls.locator(':scope > summary').click();
  return controls;
}
