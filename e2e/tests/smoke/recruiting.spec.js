import { test, expect, settle, expectNoErrorToast } from "../../fixtures.js";

async function expectPageHealthy(page) {
  await settle(page);
  await expect(page.locator("main")).not.toBeEmpty();
  await expectNoErrorToast(page);
}

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
    await first.click();
    await expect(page).toHaveURL(/\/recruiting\/postings\/\d+$/);
    await expectPageHealthy(page);
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
    await first.click();
    await expect(page).toHaveURL(/\/recruiting\/applications\/\d+/);
    await expectPageHealthy(page);
  });

  test("an open position opens for a member", async ({ as }) => {
    const page = await as("member");
    await page.goto("/recruiting/jobs");
    await settle(page);
    const first = page.locator("main .grid > button").first();
    test.skip((await first.count()) === 0, "no open positions");
    await first.click();
    await expect(page).toHaveURL(/\/recruiting\/jobs\/\d+/);
    await expectPageHealthy(page);
  });
});
