import { test, expect } from "../../fixtures.js";
import {
  idOf,
  needFlagOn,
  needSeed,
  openDetail,
  pickReviewer,
  raiseStatusRequest,
  successToast,
  waitingSection,
} from "./helpers.js";

// Mentee S1: two tabs of e2e-admin on the same detail page. One raises a
// withdrawal; the other, opened before it, sends the same request and is
// refused. The refusal shows, the page stays usable, and the first request
// is withdrawn so nothing is left pending.

test.describe(
  "refused requests",
  { tag: ["@mentorship", "@flag:matching-run"] },
  () => {
    test("a second request of the same type while one waits is refused, and the page stays usable", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const first = await as("admin");
      const stale = await as("admin");
      needSeed(stale);
      const { roundId } = stale.seed;
      const s1 = idOf(stale, "Mentee S1");
      stale.expectApiError({
        method: "POST",
        path: new RegExp(
          `^/api/mentorship/admin/rounds/${roundId}/participants/${s1}/withdraw-request$`,
        ),
        status: 409,
      });

      // The stale tab fills in the request before the other one sends it.
      await openDetail(stale, s1, roundId);
      await stale.getByRole("button", { name: "Change status / flag" }).click();
      const dialog = stale.getByRole("dialog");
      await dialog
        .getByLabel("What are you asking for")
        .selectOption({ label: "Withdraw from round" });
      await pickReviewer(dialog, reviewer.account.userId);
      await dialog.getByLabel("Reason (optional)").fill("e2e regression");

      await openDetail(first, s1, roundId);
      await raiseStatusRequest(first, {
        type: "Withdraw from round",
        reviewerId: reviewer.account.userId,
      });

      await dialog.getByRole("button", { name: "Send for approval" }).click();
      await expect(
        stale.locator('[data-sonner-toast][data-type="error"]'),
      ).toContainText(/already waiting/i);
      // Refused, the dialog stays open with what was typed, and can be left.
      await expect(dialog.getByLabel("Reason (optional)")).toHaveValue(
        "e2e regression",
      );
      await dialog.getByRole("button", { name: "Cancel" }).click();
      await expect(dialog).toBeHidden();

      // The page still works: reloaded, it shows the one request, which is
      // withdrawn from here.
      await openDetail(stale, s1, roundId);
      const row = waitingSection(stale)
        .getByRole("listitem")
        .filter({ hasText: "Withdrawal from round" });
      await expect(row).toHaveCount(1);
      await row.getByRole("button", { name: "Withdraw" }).click();
      await expect(successToast(stale, "Request withdrawn.")).toBeVisible();
      await expect(waitingSection(stale)).toHaveCount(0);
    });
  },
);
