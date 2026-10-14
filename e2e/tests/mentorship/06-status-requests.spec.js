import { test, expect } from "../../fixtures.js";
import {
  decideOnDetail,
  idOf,
  needFlagOn,
  needSeed,
  openDetail,
  raiseStatusRequest,
  roundSection,
  successToast,
  timeline,
  waitingSection,
} from "./helpers.js";

// Each test raises and decides its own request.
//   Mentee A2 + Mentor A2  withdraw approved: A2's pair ends, Mentor A2 unmatched
//   Mentee S1              withdraw rejected: nothing changes
//   Mentee A1 + Mentor A1  end pair: raised, withdrawn, raised again, approved

test.describe(
  "status requests",
  { tag: ["@mentorship", "@flag:matching-run"] },
  () => {
    test("an approved withdrawal ends the pair and unmatches the partner", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId, roundName } = page.seed;
      const mentee = idOf(page, "Mentee A2");
      const mentor = idOf(page, "Mentor A2");

      await openDetail(page, mentee, roundId);
      await raiseStatusRequest(page, {
        type: "Withdraw from round",
        reviewerId: reviewer.account.userId,
      });
      await expect(waitingSection(page)).toContainText(
        "Withdrawal from round — raised by",
      );

      await openDetail(reviewer, mentee, roundId);
      await decideOnDetail(reviewer, "Withdrawal from round", "approve");

      await openDetail(page, mentee, roundId);
      const section = roundSection(page, roundName);
      await expect(
        section.getByText("withdrawn", { exact: true }),
      ).toBeVisible();
      await expect(section.getByText("Ended", { exact: true })).toBeVisible();
      await expect(section.getByText("Active", { exact: true })).toHaveCount(0);
      await expect(waitingSection(page)).toHaveCount(0);
      const entry = timeline(page)
        .getByRole("listitem")
        .filter({ hasText: "withdrawn from this round" });
      await expect(entry).toContainText("Status change");
      await expect(entry).toContainText("(via approval)");

      await openDetail(page, mentor, roundId);
      await expect(
        roundSection(page, roundName).getByText("un_matched", { exact: true }),
      ).toBeVisible();
      await expect(
        timeline(page)
          .getByRole("listitem")
          .filter({ hasText: "their partner E2E Mentee A2 left this round" }),
      ).toHaveCount(1);
    });

    test("a withdrawal is rejected only with a reason, and nothing changes", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId, roundName } = page.seed;
      const s1 = idOf(page, "Mentee S1");

      await openDetail(page, s1, roundId);
      await raiseStatusRequest(page, {
        type: "Withdraw from round",
        reviewerId: reviewer.account.userId,
      });

      await openDetail(reviewer, s1, roundId);
      await decideOnDetail(
        reviewer,
        "Withdrawal from round",
        "reject",
        "e2e regression: not leaving",
      );

      await openDetail(page, s1, roundId);
      await expect(
        roundSection(page, roundName).getByText("signed_up", { exact: true }),
      ).toBeVisible();
      await expect(waitingSection(page)).toHaveCount(0);
    });

    test("ending a pair: raise, withdraw, raise again, then approve", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId, roundName } = page.seed;
      const mentee = idOf(page, "Mentee A1");
      const mentor = idOf(page, "Mentor A1");
      const reviewerId = reviewer.account.userId;

      await openDetail(page, mentee, roundId);
      await raiseStatusRequest(page, { type: "End this pair", reviewerId });
      const row = waitingSection(page)
        .getByRole("listitem")
        .filter({ hasText: "End pair" });
      await expect(row).toContainText("about the pair with E2E Mentor A1");

      await row.getByRole("button", { name: "Withdraw" }).click();
      await expect(successToast(page, "Request withdrawn.")).toBeVisible();
      await expect(waitingSection(page)).toHaveCount(0);

      await raiseStatusRequest(page, { type: "End this pair", reviewerId });

      // Reassigning: only one reviewer account exists, so the dialog is
      // checked (the reviewer it has and both people in the pair are left
      // out) and cancelled.
      await row.getByRole("button", { name: "Reassign" }).click();
      const reassign = page.getByRole("dialog");
      await expect(
        reassign.getByRole("heading", { name: "Reassign reviewer" }),
      ).toBeVisible();
      const picker = reassign.getByLabel("Reviewer", { exact: true });
      await expect(picker).toBeEnabled({ timeout: 15_000 });
      for (const id of [reviewerId, mentee, mentor]) {
        await expect(picker.locator(`option[value="${id}"]`)).toHaveCount(0);
      }
      await reassign.getByRole("button", { name: "Cancel" }).click();
      await expect(reassign).toBeHidden();

      // The end-pair approval opens on the mentee's page.
      await openDetail(reviewer, mentee, roundId);
      await decideOnDetail(reviewer, "End pair", "approve");

      for (const id of [mentee, mentor]) {
        await openDetail(page, id, roundId);
        const section = roundSection(page, roundName);
        await expect(section.getByText("Ended", { exact: true })).toBeVisible();
        await expect(
          section.getByText("un_matched", { exact: true }),
        ).toBeVisible();
        await expect(
          timeline(page)
            .getByRole("listitem")
            .filter({ hasText: "Pair ended; matched -> un_matched." }),
        ).toHaveCount(1);
      }
    });
  },
);
