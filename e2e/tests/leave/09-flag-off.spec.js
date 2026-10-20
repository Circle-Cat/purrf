import { test, expect, settle } from "../../fixtures.js";
import { needFlagOff } from "./helpers.js";

// With leave-management off, nothing of leave shows and every leave address
// lands on the dashboard. Runs only when the run declares the flag off.

test.describe("leave flag off", { tag: "@leave" }, () => {
  test("no card, no sidebar entry, and every leave page goes to the dashboard", async ({
    as,
  }) => {
    needFlagOff("leave-management");
    const page = await as("admin");
    await page.goto("/dashboard/me");
    await settle(page);
    await expect(page.getByText("Time off", { exact: true })).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: "Leave Administration", exact: true }),
    ).toHaveCount(0);
    for (const path of [
      "/leave/approvals",
      "/leave/requests",
      "/leave/balance-history",
      "/leave/admin",
    ]) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/dashboard\/me$/, { timeout: 20_000 });
    }
  });
});
