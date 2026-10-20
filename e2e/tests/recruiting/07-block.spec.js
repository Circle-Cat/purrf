import { test, expect } from "../../fixtures.js";
import { rowsOf } from "../../lib/seed.js";
import {
  candidateName,
  card,
  lane,
  openApplication,
  openBoard,
  pickReviewer,
  seedApplication,
  seedJob,
  successToast,
} from "./helpers.js";

// Candidate K1, whose only application is on the seeded board posting:
// the recruiter requests a block, withdraws it, requests it again, moves it
// to e2e-reviewer2, who approves on the Accounts console. The application
// is then rejected as blacklisted. Approving touches only the database (no
// Auth0 call on this path; see SIDE-EFFECTS.md), and K1 has no other
// application or meeting for the sweep to reach.

const PERSON = "Candidate K1";

async function requestBlock(page, reviewerId) {
  await page.getByRole("button", { name: "Request block" }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", {
      name: `Request a block — ${candidateName(PERSON)}`,
    }),
  ).toBeVisible();
  await pickReviewer(dialog, reviewerId);
  await dialog.getByLabel("Reason (optional)").fill("e2e regression");
  await dialog.getByRole("button", { name: "Send request" }).click();
  await expect(successToast(page, "Block requested — sent to")).toBeVisible();
  await expect(dialog).toBeHidden();
}

test.describe("block from recruiting", { tag: "@recruiting" }, () => {
  test("a block requested on an application, once approved, blacklists the applicant", async ({
    as,
  }) => {
    test.setTimeout(150_000);
    const second = await as("reviewer2");
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const k1 = seedApplication(page, PERSON);
    const name = candidateName(PERSON);
    const job = seedJob(page, "board");

    await openApplication(page, k1.applicationId, name);
    await requestBlock(page, reviewer.account.userId);
    const pending = page
      .locator("main")
      .getByText(/^Block requested — sent to /);
    await expect(pending).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Request block" }),
    ).toBeDisabled();
    await pending.getByRole("button", { name: "Withdraw" }).click();
    await expect(successToast(page, "Block request withdrawn.")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Request block" }),
    ).toBeEnabled();

    await requestBlock(page, reviewer.account.userId);
    await page
      .locator("main")
      .getByText(/^Block requested — sent to /)
      .getByRole("button", { name: "Reassign" })
      .click();
    const move = page.getByRole("dialog");
    await expect(
      move.getByRole("heading", { name: "Reassign this block request" }),
    ).toBeVisible();
    await pickReviewer(move, second.account.userId);
    await move.getByRole("button", { name: "Reassign", exact: true }).click();
    await expect(successToast(page, "Reassigned to")).toBeVisible();

    await second.goto(`/admin/accounts?user_id=${k1.userId}`);
    await second
      .getByRole("button", { name: "Approve and block" })
      .click({ timeout: 20_000 });
    const confirm = second.getByRole("dialog");
    await expect(
      confirm.getByRole("heading", { name: /^Block .*\?$/ }),
    ).toBeVisible();
    await confirm.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(confirm).toBeHidden();

    await expect
      .poll(
        () =>
          rowsOf(
            `SELECT is_blocked FROM users WHERE user_id = ${k1.userId}`,
          )[0][0],
        {
          timeout: 20_000,
        },
      )
      .toBe("t");
    expect(
      rowsOf(
        `SELECT count(*) FROM user_identities WHERE user_id = ${k1.userId}`,
      )[0][0],
      "the seed candidate has no Auth0 identity for a block to reach",
    ).toBe("0");

    await openApplication(page, k1.applicationId, name);
    const header = page.getByRole("heading", { level: 1, name }).locator("..");
    await expect(
      header.getByText("Blacklisted", { exact: true }),
    ).toBeVisible();
    await expect(header.getByText("Rejected", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Request block" }),
    ).toBeDisabled();
    await page.getByRole("tab", { name: "Timeline", exact: true }).click();
    await expect(page.getByRole("tabpanel")).toContainText(
      "Blacklisted and rejected from Recruiter screening",
    );

    await openBoard(page, job.id);
    const blocked = card(lane(page, "rejected"), k1.applicationId);
    await expect(blocked).toHaveCount(1);
    await expect(blocked).toContainText("Blacklisted");
  });
});
