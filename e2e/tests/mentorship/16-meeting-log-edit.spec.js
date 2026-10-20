import { test, expect } from "../../fixtures.js";
import {
  idOf,
  nameOf,
  needSeed,
  openDetail,
  openParticipants,
  roundSection,
  rowFor,
} from "./helpers.js";

// Mentor G1 + Mentee G1: an active pair in the live round whose one meeting
// came from Google Meet, so its log is v2 and an admin can correct it. The
// meeting is marked incomplete and the pair's count drops from 1 to 0.

test.describe("meeting log", { tag: "@mentorship" }, () => {
  test("an admin marks a v2 meeting incomplete and the count follows", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    const { roundId, roundName } = page.seed;
    const mentee = idOf(page, "Mentee G1");

    // Opening the detail page is also what lets the guard allow the edit.
    await openDetail(page, mentee, roundId);
    const section = roundSection(page, roundName);
    await expect(section.getByText("Active", { exact: true })).toBeVisible();
    await expect(section.getByText(/^Meetings 1\/\d+$/)).toBeVisible();

    await section.getByRole("button", { name: "Edit", exact: true }).click();
    await section.getByRole("combobox", { name: "Complete Status" }).click();
    await page.getByRole("option", { name: "Incomplete", exact: true }).click();
    await section.getByRole("button", { name: "Update (1)" }).click();
    const confirm = page.getByRole("dialog");
    await expect(
      confirm.getByRole("heading", { name: "Save changes?" }),
    ).toBeVisible();
    await confirm.getByRole("button", { name: "Confirm changes" }).click();
    await expect(confirm).toBeHidden();
    await expect(
      section.getByRole("button", { name: "Edit", exact: true }),
    ).toBeVisible();
    await expect(section.getByText(/^Meetings 0\/\d+$/)).toBeVisible();

    // The Participants list reads the same count, and its meeting log shows
    // the meeting as incomplete.
    await openParticipants(page, { round: roundId, id: mentee });
    const pair = rowFor(page, mentee).getByRole("listitem", {
      name: `Pair ${nameOf("Mentor G1")} and ${nameOf("Mentee G1")}`,
    });
    await pair.getByRole("button", { name: /^Meetings 0\/\d+$/ }).click();
    const log = page.getByRole("dialog");
    const rows = log.locator("tbody tr");
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText("Incomplete");
    await page.keyboard.press("Escape");
    await expect(log).toBeHidden();
  });
});
