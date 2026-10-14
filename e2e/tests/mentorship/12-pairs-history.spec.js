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

// Read-only: what the list and the detail page show about pairs and earlier
// rounds.
//   Mentor E1 + Mentee E1  active pair, one completed meeting and one Google
//                          Meet meeting Mentee E1 missed (seeded)
//   Mentee H1              withdrew after being matched to Mentor H-M1 in
//                          the previous round
//   Mentee B1              no earlier round

// A live pair is marked when one of its meetings carries an attendance tag
// (absent, late, too short: PairSection / attendanceIssueLines), not by how
// far behind its meeting count is.
const MARK = new RegExp(
  `^Attendance issues: \\d{4}-\\d{2}-\\d{2}: ${nameOf("Mentee E1")} absent$`,
);

test.describe("pairs and participation history", { tag: "@mentorship" }, () => {
  test("a pair with a missed meeting is marked, and its meeting log lists both meetings", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    const { roundId, roundName } = page.seed;
    const mentee = idOf(page, "Mentee E1");

    await openParticipants(page, { round: roundId, id: mentee });
    const pair = rowFor(page, mentee).getByRole("listitem", {
      name: `Pair ${nameOf("Mentor E1")} and ${nameOf("Mentee E1")}`,
    });
    await expect(pair.getByRole("button", { name: MARK })).toBeVisible();

    await pair.getByRole("button", { name: /^Meetings 1\/\d+$/ }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", {
        name: `Meeting Log — ${nameOf("Mentee E1")} (Mentee) with ${nameOf("Mentor E1")} (Mentor) · ${roundName}`,
      }),
    ).toBeVisible();
    await expect(dialog).toContainText("All times are in America/Los_Angeles.");
    const rows = dialog.locator("tbody tr");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toContainText("Completed");
    await expect(rows.nth(1)).toContainText("Incomplete");
    await expect(rows.nth(1)).toContainText(`${nameOf("Mentee E1")} absent`);
    // A v2 log in a round in progress can be edited; it is not, here.
    await expect(
      dialog.getByRole("button", { name: "Edit", exact: true }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();

    // The mentor's page marks the same pair.
    await openDetail(page, idOf(page, "Mentor E1"), roundId);
    const section = roundSection(page, roundName);
    await expect(section.getByText("Active", { exact: true })).toBeVisible();
    await expect(section.getByRole("button", { name: MARK })).toBeVisible();
    await expect(section.getByText(/^Meetings 1\/\d+$/)).toBeVisible();
    await expect(
      section.getByText(/^First meeting \d{4}-\d{2}-\d{2}$/),
    ).toBeVisible();
  });

  test("participation history shows an earlier round and opens it read-only", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    const { roundId } = page.seed;

    await openDetail(page, idOf(page, "Mentee B1"), roundId);
    await expect(page.getByText("No earlier rounds.")).toBeVisible();

    await openDetail(page, idOf(page, "Mentee H1"), roundId);
    const history = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Participation history" }),
    });
    const earlier = history.getByRole("listitem");
    await expect(earlier).toHaveCount(1);
    const toggle = earlier.getByRole("button", { expanded: false });
    await expect(toggle).toContainText("Mentee");
    await expect(toggle).toContainText("withdrawn");
    await expect(toggle).toContainText(`${nameOf("Mentor H-M1")} · 0/`);

    await toggle.click();
    await expect(
      earlier.getByRole("link", {
        name: `${nameOf("Mentor H-M1")} · ID ${idOf(page, "Mentor H-M1")}`,
      }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(earlier.getByText("Ended", { exact: true })).toBeVisible();
    await expect(
      earlier.getByRole("button", { name: "Add a note" }),
    ).toHaveCount(0);
  });
});
