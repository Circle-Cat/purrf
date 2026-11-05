import { test, expect, settle, expectNoErrorToast } from "../../fixtures.js";
import { NAV, canSee } from "../../lib/nav.js";

// A sidebar link's name, plus the count badge some entries carry (Inbox
// reads "Inbox 4" once its count loads and anything waits on a reply).
const sidebarLink = (page, label) =>
  page.getByRole("link", {
    name: new RegExp(
      `^${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}( \\d+)?$`,
    ),
  });

const heading = (name) => (main) =>
  main.getByRole("heading", { name, exact: true });

// What each sidebar destination shows once it has rendered: its heading, or,
// on the pages that have none, a control or card title of their own.
const LANDMARK = {
  "/dashboard/me": heading("Welcome"),
  "/dashboard": (main) => main.getByText("Include Terminated Members"),
  "/datasearch": (main) =>
    main.getByRole("button", { name: "Data Source", exact: true }),
  "/mentorship-management": (main) =>
    main.getByText("Mentorship Round Management", { exact: true }),
  "/admin/accounts": heading("Accounts"),
  "/admin/users": (main) =>
    main.getByRole("tab", { name: "Users", exact: true }),
  "/recruiting/jobs": heading("Open Positions"),
  "/inbox": heading("Inbox"),
  "/recruiting/board": heading("Applications Board"),
  "/recruiting/my-evaluations": heading("My Interview Evaluations"),
  "/recruiting/postings": heading("Job Postings"),
  "/recruiting/audit": heading("Recruiting Audit"),
  "/leave/admin": heading("Leave administration"),
  "/admin/training": heading("Training courses"),
};

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
    // The Dashboard opens on a team-wide summary that costs thousands of
    // Redis commands; the dashboard layer covers it, so smoke answers empty.
    await page.route(
      (url) => url.pathname === "/api/summary",
      (route) =>
        route.fulfill({
          json: {
            success: true,
            message: "Summary fetched successfully",
            data: [],
          },
        }),
    );
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
    const landmark = LANDMARK[item.path];
    expect(landmark, `no landmark for ${item.path}`).toBeTruthy();
    await expect(landmark(page.locator("main"))).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
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
