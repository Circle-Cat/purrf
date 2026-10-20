import { test, expect, settle, expectNoErrorToast } from "../../fixtures.js";
import { flag } from "../../lib/flags.js";
import {
  consoleErrors,
  needProfileSeed,
  openProfile,
  restoreAccountsAfterEach,
  rowsOf,
  trainingRead,
} from "./helpers.js";

// The Personal Dashboard as e2e-member (admitted as a mentee by the seed)
// and e2e-admin (who holds dashboard.activity_summary.read). The member's
// mentee onboarding is done, which the mentorship gate needs; one test
// marks it not started for a moment and restoreAccountsAfterEach puts it
// back.

restoreAccountsAfterEach();

const reminder = (page) =>
  page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "Complete onboarding training" });

const card = (page, title) =>
  page.locator('[data-slot="card"]').filter({ hasText: title });

/** The member's mentee onboarding row: [training_id, status]. */
const onboarding = (userId) =>
  rowsOf(`
    SELECT training_id, status FROM training
    WHERE user_id = ${userId} AND category = 'mentorship_mentee_onboarding'
    ORDER BY training_id`);

async function openDashboard(page) {
  await page.goto("/dashboard/me");
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(card(page, "My Applications")).toBeVisible();
}

test.describe("personal dashboard", { tag: "@profile" }, () => {
  test("unfinished onboarding training is called out on the dashboard and on the profile", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const rows = onboarding(id);
    expect(
      rows,
      "the seed gives the member one mentee onboarding",
    ).toHaveLength(1);
    expect(rows[0][1]).toBe("done");
    rowsOf(`
      UPDATE training SET status = 'to_do', completed_timestamp = NULL
      WHERE training_id = ${rows[0][0]} RETURNING training_id`);

    const read = trainingRead(page);
    await openDashboard(page);
    await read;
    const toast = reminder(page);
    await expect(toast).toBeVisible({ timeout: 15_000 });
    await expect(toast).toContainText(
      "You have been admitted to the mentorship program. Complete the onboarding training in your Profile page to get started.",
    );
    // The registration reminder of the real round may be stacked on top of
    // it, covering its button.
    await toast.getByRole("button", { name: "Confirm" }).dispatchEvent("click");
    await expect(toast).toBeHidden();

    // Once per session.
    await openDashboard(page);
    await settle(page);
    await expect(reminder(page)).toHaveCount(0);

    await openProfile(page);
    const row = page.getByTestId("training-row-required");
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("Mentee Onboarding");
    await expect(row).toContainText("Not Started");
    await expect(row.getByRole("link", { name: "Start" })).toHaveAttribute(
      "href",
      `/training/${rows[0][0]}`,
    );
  });

  test("finished onboarding raises no reminder and the member's cards load cleanly", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const errors = consoleErrors(page);
    const summaryCalls = [];
    page.on("request", (r) => {
      if (new URL(r.url()).pathname.startsWith("/api/summary"))
        summaryCalls.push(r.url());
    });
    expect(onboarding(page.account.userId)[0][1]).toBe("done");

    const read = trainingRead(page);
    await openDashboard(page);
    expect((await read).status()).toBe(200);
    await expect(card(page, "Mentorship Participation")).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
    await expect(reminder(page)).toHaveCount(0);
    await expect(card(page, "Work Activity Data")).toHaveCount(0);
    expect(summaryCalls).toEqual([]);
    await expectNoErrorToast(page);
    expect(errors).toEqual([]);

    await openProfile(page);
    await expect(page.getByTestId("training-row-required")).toHaveCount(0);
    await expect(
      page.getByTestId("training-row").filter({ hasText: "Mentee Onboarding" }),
    ).toContainText("Completed");
  });

  test("the admin's work activity card asks for this month and again on Search, and shows zeros when refused", async ({
    as,
  }) => {
    // PUR-804: the personal summary reads the ldap off a confirmed CircleCat
    // address; no test account has one, so the server refuses it (before
    // touching Redis) and the card keeps its zeros, without an error toast.
    test.skip(
      flag("view-personal-summary") !== true,
      "view-personal-summary is not declared on",
    );
    const page = await as("admin");
    const errors = consoleErrors(page);
    const summary = () =>
      page.waitForResponse(
        (r) =>
          r.request().method() === "POST" &&
          new URL(r.url()).pathname === "/api/summary/me",
        { timeout: 30_000 },
      );
    const refused = async (res) => {
      expect(res.status()).toBe(403);
      expect((await res.json()).message).toBe(
        "The activity summary needs a confirmed CircleCat address on the account.",
      );
    };
    const first = summary();
    await openDashboard(page);
    const res = await first;
    await refused(res);
    const body = res.request().postDataJSON();
    const today = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    expect(body).toEqual({
      startDate: `${today.getFullYear()}-${pad(today.getMonth() + 1)}-01`,
      endDate: `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`,
    });

    const activity = card(page, "Work Activity Data");
    for (const label of [
      "Jira Tickets (Done)",
      "Merged CLs",
      "Merged LOC",
      "Meeting Hours",
      "Chat Messages Sent",
    ]) {
      const metric = activity.getByText(label, { exact: true });
      await expect(metric).toBeVisible();
      await expect(metric.locator("xpath=following-sibling::div")).toHaveText(
        "0",
      );
    }
    const again = summary();
    await activity.getByRole("button", { name: "Search" }).click();
    await refused(await again);
    await expect(
      activity.getByRole("button", { name: "Search" }),
    ).toBeEnabled();
    await settle(page);
    await expectNoErrorToast(page);
    // The browser, the request helper and the card each log the 403;
    // nothing else.
    expect(
      errors.filter(
        (e) =>
          !/status of 403|url: \/summary\/me|Failed to fetch summary/.test(e),
      ),
    ).toEqual([]);
  });
});
