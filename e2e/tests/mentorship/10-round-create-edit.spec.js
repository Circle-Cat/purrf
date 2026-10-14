import { test, expect, settle } from "../../fixtures.js";

// Creates one round of its own, "E2E regression round <timestamp>", and
// edits only that round. No seeded people are used. cleanup.sql removes the
// round (named "E2E …", every date at least 30 days ago, nothing pointing
// at it).

const ROUNDS_PATH = "/api/mentorship/rounds";

/** The required dates, in phase order, each later than the one before. */
const DATES = [
  ["Date to send recruitment email", 2],
  ["Mentor application deadline", 3],
  ["Mentee application deadline", 3],
  ["Completion deadline", 4],
  ["Date to publish matching email", 5],
  ["Complete required meetings", 6],
];

/**
 * The create form offers dates from January 1 of last year on (RoundModal's
 * minDate); early January of last year is always more than 30 days ago, so
 * the round is never in progress or upcoming and the guard lets it through.
 */
/** A Phase Timeline date field's button, by its label (required ones end in "*"). */
const dateField = (dialog, label) =>
  dialog
    .locator("div.flex.flex-col.gap-1")
    .filter({ has: dialog.page().getByText(new RegExp(`^${label}\\*?$`)) })
    .last()
    .getByRole("button");

/** Pick one day of January of `year` in a Phase Timeline date field. */
async function pickDate(page, dialog, label, day, year) {
  const field = dateField(dialog, label);
  await field.click();
  const calendar = page.locator("[data-radix-popper-content-wrapper]").last();
  await calendar.getByLabel("Choose the Year").selectOption(String(year));
  await calendar.getByLabel("Choose the Month").selectOption("0");
  await calendar
    .getByRole("button", {
      name: new RegExp(`January ${day}(st|nd|rd|th), ${year}`),
    })
    .click();
  await page.keyboard.press("Escape");
  await expect(field).toHaveText(
    `${year} / 01 / ${String(day).padStart(2, "0")}`,
  );
}

/** The Required Meetings select of the round form. */
const requiredMeetings = (dialog) =>
  dialog.getByText("Required Meetings").locator("..").getByRole("combobox");

async function pickRequiredMeetings(page, dialog, n) {
  await requiredMeetings(dialog).click();
  await page.getByRole("option", { name: String(n), exact: true }).click();
  await expect(requiredMeetings(dialog)).toHaveText(String(n));
}

test.describe("creating and editing a round", { tag: "@mentorship" }, () => {
  test("a round created in the form is listed, and editing it saves the change", async ({
    as,
  }) => {
    const page = await as("admin");
    const name = `E2E regression round ${Date.now()}`;
    const year = new Date().getFullYear() - 1;

    await page.goto("/mentorship-management");
    await expect(page.getByText("Mentorship Round Management")).toBeVisible();
    await settle(page);

    await page.getByRole("button", { name: "Create New Round" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Create New Round" }),
    ).toBeVisible();
    await dialog.getByLabel("Round Name").fill(name);
    await pickRequiredMeetings(page, dialog, 3);
    for (const [label, day] of DATES) {
      await pickDate(page, dialog, label, day, year);
    }

    const created = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        new URL(r.url()).pathname === ROUNDS_PATH,
    );
    await dialog.getByRole("button", { name: "Save", exact: true }).click();
    const round = (await (await created).json()).data;
    expect(round.name).toBe(name);
    expect(round.timeline.meetingsCompletionDeadlineAt).toMatch(
      new RegExp(`^${year}-`),
    );
    await expect(dialog).toBeHidden();

    const table = page.locator("table").first();
    const row = table.locator("tbody tr").filter({
      has: page.getByRole("cell", { name, exact: true }),
    });
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("3 times");

    await row.getByRole("button", { name: "Edit round" }).click();
    await expect(
      dialog.getByRole("heading", { name: "Edit Round" }),
    ).toBeVisible();
    await expect(dialog.getByLabel("Round Name")).toHaveValue(name);
    await expect(requiredMeetings(dialog)).toHaveText("3");
    await expect(dateField(dialog, "Complete required meetings")).toHaveText(
      `${year} / 01 / 06`,
    );

    await pickRequiredMeetings(page, dialog, 4);
    const saved = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        new URL(r.url()).pathname === ROUNDS_PATH,
    );
    await dialog.getByRole("button", { name: "Save", exact: true }).click();
    const edited = (await (await saved).json()).data;
    expect(edited.id).toBe(round.id);
    expect(edited.requiredMeetings).toBe(4);
    await expect(dialog).toBeHidden();
    await expect(row).toContainText("4 times");
  });
});
