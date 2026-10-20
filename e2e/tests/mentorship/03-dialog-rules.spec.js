import { test, expect } from "../../fixtures.js";
import {
  idOf,
  needFlagOn,
  needSeed,
  openDetail,
  optionLabels,
  optionValues,
  timeline,
} from "./helpers.js";

// Read-only: dialogs are opened and cancelled, nothing is sent. Runs before
// the files that change these people.
//   Mentee S1  signed up, no pair: no "Mark as no show"
//   Mentee W1  withdrawn, ended pair: no "Withdraw from round"
//   Mentee H1  in the previous round: read-only page

test.describe("change status dialog rules", { tag: "@mentorship" }, () => {
  test(
    "a signed-up person with no pair cannot be marked as a no show; reviewers leave out the raiser and the person",
    { tag: "@flag:matching-run" },
    async ({ as }) => {
      needFlagOn("matching-run");
      const page = await as("admin");
      needSeed(page);
      const s1 = idOf(page, "Mentee S1");
      await openDetail(page, s1, page.seed.roundId);

      await page.getByRole("button", { name: "Change status / flag" }).click();
      const dialog = page.getByRole("dialog");
      const types = await optionLabels(
        dialog.getByLabel("What are you asking for"),
      );
      expect(types).toContain("Withdraw from round");
      expect(types).toContain("Raise a red flag");
      expect(types).not.toContain("Mark as no show");
      expect(types).not.toContain("End this pair");

      const reviewers = dialog.getByLabel("Reviewer", { exact: true });
      await expect(reviewers).toBeEnabled({ timeout: 15_000 });
      const values = await optionValues(reviewers);
      expect(values).not.toContain(String(page.account.userId));
      expect(values).not.toContain(String(s1));
      await expect(
        dialog.getByText(
          "E2E Mentee S1 cannot review a request about themselves.",
        ),
      ).toBeVisible();

      await dialog.getByRole("button", { name: "Cancel" }).click();
      await expect(dialog).toBeHidden();
    },
  );

  test(
    "a withdrawn person cannot be withdrawn again but can be marked on their ended pair",
    { tag: "@flag:matching-run" },
    async ({ as }) => {
      needFlagOn("matching-run");
      const page = await as("admin");
      needSeed(page);
      await openDetail(page, idOf(page, "Mentee W1"), page.seed.roundId);

      await page.getByRole("button", { name: "Change status / flag" }).click();
      const dialog = page.getByRole("dialog");
      const typeSelect = dialog.getByLabel("What are you asking for");
      const types = await optionLabels(typeSelect);
      expect(types).not.toContain("Withdraw from round");
      expect(types).not.toContain("End this pair");
      expect(types).toContain("Mark as no show");

      // A no show must name a pair; the only one, ended, is picked.
      await typeSelect.selectOption({ label: "Mark as no show" });
      const pair = dialog.getByLabel("Which pair");
      await expect(pair.locator("option:checked")).toHaveText(
        "E2E Mentor W-M1 (ended)",
      );

      await dialog.getByRole("button", { name: "Cancel" }).click();
      await expect(dialog).toBeHidden();
    },
  );

  test("a round not in progress is read-only", async ({ as }) => {
    const page = await as("admin");
    needSeed(page);
    await openDetail(page, idOf(page, "Mentee H1"), page.seed.prevRoundId);

    await expect(
      page.getByText("This round is not in progress. The page is read-only."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Change status / flag" }),
    ).toHaveCount(0);
    await expect(
      timeline(page).getByRole("button", { name: "Add a note" }),
    ).toHaveCount(0);
    await expect(
      timeline(page).getByRole("button", { name: "Mark as notified" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Edit", exact: true }),
    ).toHaveCount(0);
  });
});
