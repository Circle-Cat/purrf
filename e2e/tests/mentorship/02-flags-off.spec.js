import { test, expect, settle } from "../../fixtures.js";
import {
  idOf,
  needFlagOff,
  needSeed,
  openDetail,
  openParticipants,
  timeline,
} from "./helpers.js";

// Read-only checks of what is hidden while a flag is declared off.
// People: Mentee S1 (detail page only).

test.describe("mentorship with flags off", { tag: "@mentorship" }, () => {
  test(
    "matching-run off: no run, no results, no status requests",
    { tag: "@flag:matching-run" },
    async ({ as }) => {
      needFlagOff("matching-run");
      const page = await as("admin");
      needSeed(page);
      const { roundId } = page.seed;

      await openParticipants(page, { round: roundId, eligible: "1" });
      await expect(
        page.getByRole("button", { name: /^Run matching/ }),
      ).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "View matching results" }),
      ).toHaveCount(0);

      await page.goto(`/mentorship-management/matching/${roundId}`);
      await expect(
        page.getByText("Matching runs are not available."),
      ).toBeVisible({ timeout: 20_000 });

      await openDetail(page, idOf(page, "Mentee S1"), roundId);
      await expect(
        page.getByRole("button", { name: "Change status / flag" }),
      ).toHaveCount(0);
    },
  );

  test(
    "mentorship-kit-email off: no Mark as notified, no notification filter",
    { tag: "@flag:mentorship-kit-email" },
    async ({ as }) => {
      needFlagOff("mentorship-kit-email");
      const page = await as("admin");
      needSeed(page);
      const { roundId } = page.seed;

      await openDetail(page, idOf(page, "Mentee S1"), roundId);
      await expect(
        timeline(page).getByRole("button", { name: "Add a note" }),
      ).toBeVisible();
      await expect(
        timeline(page).getByRole("button", { name: "Mark as notified" }),
      ).toHaveCount(0);

      await openParticipants(page, { round: roundId });
      await settle(page);
      await expect(
        page.getByRole("button", { name: "Notification filter" }),
      ).toHaveCount(0);
    },
  );
});
