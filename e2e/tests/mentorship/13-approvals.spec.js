import { test, expect, settle } from "../../fixtures.js";
import {
  decideOnDetail,
  idOf,
  nameOf,
  needFlagOn,
  needSeed,
  openDetail,
  openParticipants,
  pickReviewer,
  raiseStatusRequest,
  rowFor,
  successToast,
  waitingSection,
} from "./helpers.js";

// Each test raises its own request and leaves nothing pending; every
// request ends rejected, so nobody's status changes.
//   Mentee E1  withdrawal, found on the reviewer's Pending approvals card
//   Mentee H2  exemption, rejected (H2 keeps needing one)
//   Mentor E1  withdrawal, reassigned from e2e-reviewer to e2e-reviewer2

/** The reviewer's Pending approvals card on Mentorship Management. */
async function pendingCard(page) {
  await page.goto("/mentorship-management");
  await expect(page.getByText("Mentorship Round Management")).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
  return page
    .locator('[data-slot="card"]')
    .filter({ hasText: "Pending approvals" });
}

test.describe(
  "approvals",
  { tag: ["@mentorship", "@flag:matching-run"] },
  () => {
    test("a request waiting on the reviewer is on their Pending approvals card and Review opens its page", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId, roundName } = page.seed;
      const id = idOf(page, "Mentee E1");
      const reason = `e2e regression ${Date.now()}`;

      await openDetail(page, id, roundId);
      await raiseStatusRequest(page, {
        type: "Withdraw from round",
        reviewerId: reviewer.account.userId,
        reason,
      });

      const card = await pendingCard(reviewer);
      const item = card.getByRole("listitem").filter({ hasText: reason });
      await expect(item).toHaveCount(1);
      await expect(item).toContainText(
        `Withdrawal from round · ${roundName} · ${nameOf("Mentee E1")}`,
      );
      await expect(item).toContainText("From ");
      await item.getByRole("button", { name: "Review" }).click();
      await expect(reviewer).toHaveURL(
        new RegExp(
          `/mentorship-management/participants/${id}\\?round=${roundId}$`,
        ),
      );
      await expect(
        reviewer.getByRole("heading", { level: 2, name: nameOf("Mentee E1") }),
      ).toBeVisible({ timeout: 20_000 });
      await settle(reviewer);

      await decideOnDetail(
        reviewer,
        "Withdrawal from round",
        "reject",
        "e2e regression: staying",
      );
      await expect(waitingSection(reviewer)).toHaveCount(0);
      const after = await pendingCard(reviewer);
      await expect(
        after.getByRole("listitem").filter({ hasText: reason }),
      ).toHaveCount(0);
    });

    test("an exemption is rejected only with a reason, and the person still needs one", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId } = page.seed;
      const h2 = idOf(page, "Mentee H2");
      const list = { round: roundId, id: h2, needsExemption: "1" };

      await openParticipants(page, list);
      await rowFor(page, h2)
        .getByRole("button", { name: "Request exemption" })
        .click();
      const dialog = page.getByRole("dialog");
      await pickReviewer(dialog, reviewer.account.userId);
      await dialog.getByLabel("Reason (optional)").fill("e2e regression");
      await dialog.getByRole("button", { name: "Send request" }).click();
      await expect(successToast(page, "Sent for approval.")).toBeVisible();

      await openParticipants(reviewer, list);
      await rowFor(reviewer, h2)
        .getByRole("button", { name: "Reject", exact: true })
        .click();
      const decide = reviewer.getByRole("dialog");
      await expect(
        decide.getByRole("heading", {
          name: `Reject the exemption for ${nameOf("Mentee H2")}`,
        }),
      ).toBeVisible();
      const reject = decide.getByRole("button", {
        name: "Reject",
        exact: true,
      });
      await expect(reject, "a rejection needs a reason").toBeDisabled();
      await decide.getByLabel("Reason", { exact: true }).fill("   ");
      await expect(reject, "blank is no reason").toBeDisabled();
      await decide
        .getByLabel("Reason", { exact: true })
        .fill("e2e regression: not exempt");
      await reject.click();
      await expect(successToast(reviewer, "Exemption rejected.")).toBeVisible();

      await openParticipants(page, list);
      const row = rowFor(page, h2);
      await expect(row).toHaveCount(1);
      await expect(row).not.toContainText("Waiting for approval");
      await expect(
        row.getByRole("button", { name: "Request exemption" }),
      ).toBeVisible();
      await openParticipants(page, { round: roundId, id: h2, eligible: "1" });
      await expect(rowFor(page, h2)).toHaveCount(0);
    });

    test("a request reassigned to another reviewer moves to them", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const second = await as("reviewer2");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId } = page.seed;
      const id = idOf(page, "Mentor E1");

      await openDetail(page, id, roundId);
      await raiseStatusRequest(page, {
        type: "Withdraw from round",
        reviewerId: reviewer.account.userId,
      });
      const row = waitingSection(page)
        .getByRole("listitem")
        .filter({ hasText: "Withdrawal from round" });
      await row.getByRole("button", { name: "Reassign" }).click();
      const dialog = page.getByRole("dialog");
      await expect(
        dialog.getByRole("heading", { name: "Reassign reviewer" }),
      ).toBeVisible();
      await pickReviewer(dialog, second.account.userId);
      await dialog
        .getByRole("button", { name: "Reassign", exact: true })
        .click();
      await expect(successToast(page, "Request reassigned.")).toBeVisible();

      // The first reviewer can no longer decide it; the second can.
      await openDetail(reviewer, id, roundId);
      const theirs = waitingSection(reviewer)
        .getByRole("listitem")
        .filter({ hasText: "Withdrawal from round" });
      await expect(theirs).toHaveCount(1);
      await expect(
        theirs.getByRole("button", { name: "Approve", exact: true }),
      ).toHaveCount(0);

      await openDetail(second, id, roundId);
      await decideOnDetail(
        second,
        "Withdrawal from round",
        "reject",
        "e2e regression: staying",
      );
      await openDetail(page, id, roundId);
      await expect(waitingSection(page)).toHaveCount(0);
    });
  },
);
