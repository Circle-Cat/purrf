import { test, expect } from "../../fixtures.js";
import {
  idOf,
  nameOf,
  needFlagOn,
  needSeed,
  openDetail,
  openParticipants,
  rowFor,
  successToast,
  timeline,
} from "./helpers.js";

// Notes and marks of notification change no status.
//   Mentee B2  a note; marked as notified of the mid-term reminder, then found by
//              the Participants notification filter
//   Mentor B1  the Send email dialog, opened and cancelled (sending is
//              always blocked by the guard)

test.describe("notes, notifications and email", { tag: "@mentorship" }, () => {
  test("a note is added to the timeline", async ({ as }) => {
    const page = await as("admin");
    needSeed(page);
    const id = idOf(page, "Mentee B2");
    const body = `E2E regression note ${Date.now()}`;

    await openDetail(page, id, page.seed.roundId);
    await timeline(page).getByRole("button", { name: "Add a note" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Add a note" }),
    ).toBeVisible();
    const save = dialog.getByRole("button", { name: "Save note" });
    await expect(save).toBeDisabled();
    await dialog.getByLabel("Note", { exact: true }).fill(body);
    await save.click();
    await expect(dialog).toBeHidden();
    await expect(
      timeline(page).getByRole("listitem").filter({ hasText: body }),
    ).toHaveCount(1);
  });

  test(
    "marked as notified, the person is on the timeline and found by the notification filter",
    { tag: "@flag:mentorship-kit-email" },
    async ({ as }) => {
      needFlagOn("mentorship-kit-email");
      const page = await as("admin");
      needSeed(page);
      const { roundId } = page.seed;
      const id = idOf(page, "Mentee B2");
      const how = `E2E regression: told on Teams ${Date.now()}`;

      await openDetail(page, id, roundId);
      await timeline(page)
        .getByRole("button", { name: "Mark as notified" })
        .click();
      const dialog = page.getByRole("dialog");
      await expect(
        dialog.getByRole("heading", {
          name: `Mark as notified — ${nameOf("Mentee B2")}`,
        }),
      ).toBeVisible();
      await dialog
        .getByLabel("Which notification")
        .selectOption({ label: "Mid-term reminder" });
      await dialog.getByLabel("How it was sent").fill(how);
      await dialog
        .getByRole("button", { name: "Mark as notified · 1" })
        .click();
      await expect(successToast(page, "Marked 1 as notified")).toBeVisible();
      const entry = timeline(page)
        .getByRole("listitem")
        .filter({ hasText: how });
      await expect(entry).toContainText(
        "Marked as notified: Mid-term reminder",
      );

      // The filter is picked in the UI, then searched.
      await openParticipants(page, { round: roundId, id });
      await page.getByRole("button", { name: "Notification filter" }).click();
      await page.getByRole("menuitem", { name: "Mid-term reminder" }).hover();
      await page
        .getByRole("menuitem", { name: "Notified", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Notification filter" }),
      ).toHaveText("Mid-term reminder · Notified");
      await page.getByRole("button", { name: "Search", exact: true }).click();
      await expect(page).toHaveURL(/notifyStage=midterm_reminder/);
      await expect(page).toHaveURL(/notifyState=notified/);
      await expect(rowFor(page, id)).toContainText(
        "Mid-term reminder · Notified manually",
      );

      // And the opposite filter leaves them out.
      await openParticipants(page, {
        round: roundId,
        id,
        notifyStage: "midterm_reminder",
        notifyState: "not_notified",
      });
      await expect(rowFor(page, id)).toHaveCount(0);
    },
  );

  test("Send email opens addressed only to that person; nothing is sent", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    const send = page.getByRole("button", { name: "Send email" });
    await openDetail(page, idOf(page, "Mentor B1"), page.seed.roundId);
    test.skip(
      (await send.count()) === 0,
      "no sender is set up for participant email in this environment",
    );

    await send.click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Send email" }),
    ).toBeVisible();
    const to = dialog.getByRole("group", { name: "To" });
    await expect(to.getByRole("checkbox")).toHaveCount(1);
    await expect(to.getByRole("checkbox")).toBeChecked();
    await expect(to).toContainText("e2e.mentor.b1@e2e.purrf.test");

    // Stop here: the guard aborts any send and would fail the test.
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
  });
});
