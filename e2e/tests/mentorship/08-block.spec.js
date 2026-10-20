import { test, expect } from "../../fixtures.js";
import {
  idOf,
  nameOf,
  needSeed,
  openDetail,
  pickReviewer,
  roundSection,
  successToast,
} from "./helpers.js";

// Mentee C1: block requested from the mentorship page, approved on the
// account console; C1's active pair with Mentor C1 must end.
//
// Block requests are decided by user.admin holders. Without it the reviewer
// account cannot be named, and the test is skipped rather than sending the
// request to a real person.

const PERSON = "Mentee C1";

test.describe("block from Purrf", { tag: "@mentorship" }, () => {
  test("a block request, once approved, blocks the person and their pairs end", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    const page = await as("admin");
    needSeed(page);
    test.skip(
      !reviewer.account.permissions.includes("user.admin"),
      "the reviewer account does not hold user.admin, so it cannot decide a block",
    );
    const { roundId, roundName } = page.seed;
    const id = idOf(page, PERSON);
    const header = page
      .getByRole("heading", { level: 2, name: nameOf(PERSON) })
      .locator("..");

    await openDetail(page, id, roundId);
    const section = roundSection(page, roundName);
    await expect(section.getByText("Active", { exact: true })).toHaveCount(1);
    await page.getByRole("button", { name: "Block from Purrf" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", {
        name: `Request a block — ${nameOf(PERSON)}`,
      }),
    ).toBeVisible();
    await pickReviewer(dialog, reviewer.account.userId);
    await dialog.getByLabel("Reason (optional)").fill("e2e regression");
    await dialog.getByRole("button", { name: "Send request" }).click();
    await expect(successToast(page, "Block requested — sent to")).toBeVisible();
    await expect(page.getByText(/^Block requested — sent to /)).toBeVisible();

    await reviewer.goto(`/admin/accounts?user_id=${id}`);
    await reviewer
      .getByRole("button", { name: "Approve and block" })
      .click({ timeout: 20_000 });
    const confirm = reviewer.getByRole("dialog");
    await expect(
      confirm.getByRole("heading", { name: /^Block .*\?$/ }),
    ).toBeVisible();
    await confirm.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(confirm).toBeHidden();

    // PUR-778: the first load right after the approval can show the block's
    // timeline note next to the old status and active pair, while the
    // database already holds the new state. #742 made the dialog wait for
    // the request; the detail read that spans commits is still open. Record
    // it when it happens rather than hiding it, then wait for the settled
    // page.
    await openDetail(page, id, roundId);
    const blocked = header.getByText("Blocked", { exact: true });
    if (!(await blocked.isVisible())) {
      test.info().annotations.push({
        type: "stale read",
        description:
          "detail page loaded right after the block approval still showed the person unblocked",
      });
      await expect(async () => {
        await openDetail(page, id, roundId);
        await expect(blocked).toBeVisible({ timeout: 2_000 });
      }).toPass({ timeout: 30_000 });
    }
    await expect(
      page.getByRole("button", { name: "Block from Purrf" }),
    ).toHaveCount(0);
    await expect(section.getByText("Active", { exact: true })).toHaveCount(0);
  });
});
