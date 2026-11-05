import { test, expect, settle, expectNoErrorToast } from "../../fixtures.js";

/** The page opened on what it was asked for: its title is the h1. */
async function expectPageHealthy(page, title) {
  await expect(
    page.getByRole("heading", { level: 1, name: title, exact: true }),
  ).toBeVisible({ timeout: 20_000 });
  await settle(page);
  await expectNoErrorToast(page);
}

/** The first line of a list row or board card: its title or name. */
const firstLine = async (row) =>
  (await row.locator("p").first().textContent()).trim();

test.describe("recruiting pages", { tag: "@smoke" }, () => {
  test("a job posting opens from Job Postings", async ({ as }) => {
    const page = await as("admin");
    await page.goto("/recruiting/postings");
    await expect(
      page.getByRole("heading", { name: "Job Postings" }),
    ).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
    const first = page
      .getByRole("button")
      .filter({ hasText: "Recruiter:" })
      .first();
    test.skip((await first.count()) === 0, "no postings");
    const title = await firstLine(first);
    await first.click();
    await expect(page).toHaveURL(/\/recruiting\/postings\/\d+$/);
    await expectPageHealthy(page, title);
  });

  test("an application opens from the Applications Board", async ({ as }) => {
    const page = await as("admin");
    await page.goto("/recruiting/board");
    await expect(
      page.getByRole("heading", { name: "Applications Board" }),
    ).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
    const first = page.getByRole("button").filter({ hasText: / UTC$/ }).first();
    test.skip(
      (await first.count()) === 0,
      "no applications on the default posting",
    );
    const name = await firstLine(first);
    await first.click();
    await expect(page).toHaveURL(/\/recruiting\/applications\/\d+/);
    await expectPageHealthy(page, name);
  });

  test("an open position opens for a member", async ({ as }) => {
    const page = await as("member");
    await page.goto("/recruiting/jobs");
    await expect(
      page.getByRole("heading", { level: 1, name: "Open Positions" }),
    ).toBeVisible({ timeout: 20_000 });
    await settle(page);
    const first = page.locator("main .grid > button").first();
    test.skip((await first.count()) === 0, "no open positions");
    const title = await firstLine(first);
    await first.click();
    await expect(page).toHaveURL(/\/recruiting\/jobs\/\d+/);
    await expectPageHealthy(page, title);
  });
});
