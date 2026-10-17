// Existing-work journeys choose their entry explicitly, just as an owner does.
export async function chooseExisting(page) {
  await page.getByRole('dialog', { name: 'Welcome to HuntMaps2', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Open existing work', exact: true }).click();
}
export async function openExisting(page, url) {
  await page.goto(url);
  await chooseExisting(page);
}
export async function reloadExisting(page) {
  await page.reload();
  await chooseExisting(page);
}
