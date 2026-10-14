import { test, expect, settle, expectNoErrorToast } from "../../fixtures.js";
import { NAV, canSee } from "../../lib/nav.js";

const sidebarLink = (page, label) =>
  page.getByRole("link", { name: label, exact: true });

for (const role of ["admin", "reviewer", "member"]) {
  test(
    `${role} sees the sidebar their permissions allow`,
    { tag: "@smoke" },
    async ({ as }) => {
      const page = await as(role);
      await page.goto("/");
      await expect(sidebarLink(page, "Personal Dashboard")).toBeVisible({
        timeout: 20_000,
      });
      const { permissions } = page.account;
      for (const item of NAV) {
        const link = sidebarLink(page, item.label);
        if (!canSee(item, permissions)) {
          await expect(link, `${item.label} should be hidden`).toHaveCount(0);
        } else if (!item.flagged) {
          await expect(link, `${item.label} should be shown`).toBeVisible();
        }
      }
    },
  );
}

for (const item of NAV) {
  test(`admin opens ${item.label}`, { tag: "@smoke" }, async ({ as }) => {
    const page = await as("admin");
    test.skip(!canSee(item, page.account.permissions), "admin cannot see it");
    await page.goto("/");
    const link = sidebarLink(page, item.label);
    await expect(sidebarLink(page, "Personal Dashboard")).toBeVisible({
      timeout: 20_000,
    });
    // Flagged entries appear only once LaunchDarkly has answered.
    if (item.flagged) await settle(page);
    test.skip(
      item.flagged && (await link.count()) === 0,
      "feature flag is off",
    );
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${item.path}(\\?|$)`));
    await settle(page);
    await expect(page.locator("main")).not.toBeEmpty();
    await expectNoErrorToast(page);
    await page.screenshot({
      path: test.info().outputPath("page.png"),
      fullPage: true,
    });
  });
}

test(
  "member is turned away from admin pages",
  { tag: "@smoke" },
  async ({ as }) => {
    const page = await as("member");
    for (const item of NAV.filter(
      (i) => !canSee(i, page.account.permissions),
    )) {
      await page.goto(item.path);
      await expect(page, `${item.path} should be refused`).toHaveURL(
        /\/access-denied$/,
      );
    }
  },
);
