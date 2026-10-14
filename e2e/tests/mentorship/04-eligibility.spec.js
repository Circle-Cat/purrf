import { test, expect } from "../../fixtures.js";
import {
  idOf,
  needFlagOn,
  needSeed,
  openParticipants,
  pickReviewer,
  rowFor,
  successToast,
} from "./helpers.js";

// People:
//   Mentor B1, Mentor B2, Mentee B1, Mentee B2, e2e-member  eligible (read only)
//   Mentee H1  exemption requested and approved (H1 becomes eligible)
// The list check runs first, while H1 still needs the exemption.

const SEEDED = "@e2e.purrf.test";

test.describe("matching eligibility", { tag: "@mentorship" }, () => {
  test("Eligible for matching lists the waiting group, not the person needing an exemption", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    const { roundId, memberId } = page.seed;

    await openParticipants(page, { round: roundId, q: SEEDED, eligible: "1" });
    for (const name of ["Mentor B1", "Mentor B2", "Mentee B1", "Mentee B2"]) {
      await expect(rowFor(page, idOf(page, name)), name).toHaveCount(1);
    }
    // H1 needs an exemption, A1 has no open slot, W1 has withdrawn.
    for (const name of ["Mentee H1", "Mentee A1", "Mentee W1"]) {
      await expect(rowFor(page, idOf(page, name)), name).toHaveCount(0);
    }

    // e2e-member's address is not a seeded one; look them up by id.
    await openParticipants(page, {
      round: roundId,
      id: memberId,
      eligible: "1",
    });
    await expect(rowFor(page, memberId)).toHaveCount(1);

    await openParticipants(page, {
      round: roundId,
      q: SEEDED,
      needsExemption: "1",
    });
    const h1 = rowFor(page, idOf(page, "Mentee H1"));
    await expect(h1).toHaveCount(1);
    await expect(h1).toContainText(
      /Quit after being matched in (?!this round)/,
    );
    await expect(rowFor(page, idOf(page, "Mentor B1"))).toHaveCount(0);
  });

  test(
    "an approved exemption makes the person eligible",
    { tag: "@flag:matching-run" },
    async ({ as }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId } = page.seed;
      const h1 = idOf(page, "Mentee H1");
      const list = { round: roundId, id: h1, needsExemption: "1" };

      await openParticipants(page, list);
      await rowFor(page, h1)
        .getByRole("button", { name: "Request exemption" })
        .click();
      const dialog = page.getByRole("dialog");
      await expect(
        dialog.getByRole("heading", {
          name: "Request an exemption for E2E Mentee H1",
        }),
      ).toBeVisible();
      await pickReviewer(dialog, reviewer.account.userId);
      await dialog.getByLabel("Reason (optional)").fill("e2e regression");
      await dialog.getByRole("button", { name: "Send request" }).click();
      await expect(successToast(page, "Sent for approval.")).toBeVisible();
      await expect(rowFor(page, h1)).toContainText(
        "Waiting for approval — sent to",
      );

      // The reviewer decides from the link the approval points at.
      await openParticipants(reviewer, list);
      const row = rowFor(reviewer, h1);
      await row.getByRole("button", { name: "Approve", exact: true }).click();
      const decide = reviewer.getByRole("dialog");
      await expect(
        decide.getByRole("heading", { name: "Exempt E2E Mentee H1" }),
      ).toBeVisible();
      await decide
        .getByRole("button", { name: "Approve", exact: true })
        .click();
      await expect(successToast(reviewer, "Exemption granted.")).toBeVisible();

      await openParticipants(page, { round: roundId, id: h1, eligible: "1" });
      await expect(rowFor(page, h1)).toHaveCount(1);
      await openParticipants(page, list);
      await expect(rowFor(page, h1)).toHaveCount(0);
    },
  );
});
