import { test, expect, settle } from "../../fixtures.js";
import { needSeed } from "./helpers.js";

// Read-only: opens the seeded live round's form and cancels it.

test.describe("mentorship rounds", { tag: "@mentorship" }, () => {
  test("the edit form of the round in progress shows its data and is cancelled", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    const roundsLoaded = page.waitForResponse(
      (r) => r.url().includes("/api/mentorship/rounds?need_details=true"),
      { timeout: 30_000 },
    );
    await page.goto("/mentorship-management");
    const rounds = (await (await roundsLoaded).json()).data;
    await expect(page.getByText("Mentorship Round Management")).toBeVisible();
    await settle(page);

    const round = rounds.find((r) => r.id === page.seed.roundId);
    expect(round, "the seeded live round is listed").toBeTruthy();
    expect(round.isInProgress).toBe(true);

    const table = page.locator("table").first();
    await expect(table.locator("tbody tr")).toHaveCount(rounds.length);
    const row = table.locator("tbody tr").filter({
      has: page.getByRole("cell", { name: round.name, exact: true }),
    });
    await expect(row).toHaveCount(1);
    if (round.requiredMeetings != null) {
      await expect(row).toContainText(`${round.requiredMeetings} times`);
    }

    await row.getByRole("button", { name: "Edit round" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Edit Round" }),
    ).toBeVisible();
    await expect(dialog.getByLabel("Round Name")).toHaveValue(round.name);
    if (round.requiredMeetings != null) {
      await expect(
        dialog
          .getByText("Required Meetings")
          .locator("..")
          .getByRole("combobox"),
      ).toHaveText(String(round.requiredMeetings));
    }
    await expect(dialog.getByText("Phase Timeline")).toBeVisible();

    // Never saved: Cancel closes it and nothing is sent.
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
  });
});
