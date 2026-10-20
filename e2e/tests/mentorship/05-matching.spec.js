import { test, expect, settle } from "../../fixtures.js";
import { flag } from "../../lib/flags.js";
import {
  idOf,
  needFlagOn,
  needSeed,
  openDetail,
  openMemberDashboard,
  openParticipants,
  pickReviewer,
  roundSection,
  rowFor,
  successToast,
} from "./helpers.js";

// One chain in the seeded live round, run in order and stopped at the first
// failure: the results to edit and publish are the first test's run, and the
// member's meetings need the published pair.
//   Mentor B1, Mentor B2, Mentee B1, Mentee B2, e2e-member  the run, the
//     published pairs; e2e-member also logs a meeting.
// Nobody else is picked, so the run touches no real person.

const RUN_GROUP = ["Mentor B1", "Mentor B2", "Mentee B1", "Mentee B2"];
const PARTNER = /E2E Mentor B[12]/;
const EDITED_REASON = "E2E regression: reason edited in the draft.";

/** Wait for the Participants list to answer after paging. */
const listAnswered = (page) =>
  page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname.endsWith("/mentorship/admin/participants"),
    { timeout: 30_000 },
  );

/** Tick these people in the list, paging on; picks survive paging. */
async function tickAcrossPages(page, ids) {
  const left = new Set(ids);
  for (;;) {
    for (const id of [...left]) {
      const row = rowFor(page, id);
      if ((await row.count()) === 1) {
        await row.getByRole("checkbox").check();
        left.delete(id);
      }
    }
    if (left.size === 0) return;
    const next = page.getByRole("button", { name: "Next", exact: true });
    if (await next.isDisabled()) {
      throw new Error(`not in Eligible for matching: ${[...left].join(", ")}`);
    }
    const answered = listAnswered(page);
    await next.click();
    await answered;
    await settle(page);
  }
}

/** The meeting form's date button reads like "October 20th, 2026". */
const FORM_DATE = /^([A-Z][a-z]+) (\d{1,2})(?:st|nd|rd|th), (\d{4})$/;

const ordinal = (n) => {
  if (n % 100 >= 11 && n % 100 <= 13) return `${n}th`;
  return `${n}${{ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th"}`;
};

/**
 * Move the meeting form's date one day back. The form starts on today in the
 * member's time zone, which can differ from the browser's, so the day before
 * is worked out from the date the form shows.
 */
async function pickDayBefore(member, dialog) {
  const button = dialog.getByRole("button", { name: FORM_DATE });
  const [, month, day, year] = (await button.innerText())
    .trim()
    .match(FORM_DATE);
  const date = new Date(`${month} ${day}, ${year}`);
  date.setDate(date.getDate() - 1);
  const before = `${date.toLocaleString("en-US", { month: "long" })} ${ordinal(
    date.getDate(),
  )}, ${date.getFullYear()}`;
  await button.click();
  // Day buttons are labelled like "Monday, October 19th, 2026".
  const dayButton = member.getByRole("button", {
    name: new RegExp(`, ${before}(, selected)?$`),
  });
  if ((await dayButton.count()) === 0) {
    await member
      .getByRole("button", { name: "Go to the Previous Month" })
      .click();
  }
  await dayButton.first().click();
  await expect(button).toHaveText(before);
  // Picking a day leaves the calendar open; Escape closes only the calendar.
  const calendar = member.getByRole("grid");
  if (await calendar.isVisible()) await member.keyboard.press("Escape");
  await expect(calendar).toBeHidden();
  await expect(dialog).toBeVisible();
}

/** One mentee's row on the results page, by the "ID <n>" in it. */
const resultRow = (page, userId) =>
  page.locator("li").filter({ hasText: new RegExp(`ID ${userId}\\b`) });

test.describe(
  "matching, publishing and the member's round",
  { tag: ["@mentorship", "@flag:matching-run"] },
  () => {
    test.describe.configure({ mode: "serial" });

    test("a run over the waiting group finishes and its results load", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const page = await as("admin");
      needSeed(page);
      test.setTimeout(10 * 60_000);
      const { roundId, roundName, memberId } = page.seed;
      const ids = [...RUN_GROUP.map((n) => idOf(page, n)), memberId];

      // Newest ids first, so the seeded people sit on the first page.
      await openParticipants(page, {
        round: roundId,
        eligible: "1",
        sort: "user_id",
        order: "desc",
      });
      await tickAcrossPages(page, ids);

      const run = page.getByRole("button", { name: "Run matching · 5" });
      await expect(run).toBeEnabled();
      await run.click();
      const dialog = page.getByRole("dialog");
      await expect(
        dialog.getByRole("heading", { name: `Run matching for ${roundName}?` }),
      ).toBeVisible();
      await expect(dialog).toContainText("2 mentors and 3 mentees.");
      await dialog.getByRole("button", { name: "Run", exact: true }).click();
      await expect(page).toHaveURL(
        new RegExp(`/mentorship-management/matching/${roundId}$`),
      );

      // The page does not refresh itself; reload until the run is over.
      await expect(async () => {
        await page.reload();
        await expect(
          page.getByText(/^(Succeeded|Failed|Unusable)$/),
        ).toBeVisible({ timeout: 10_000 });
      }).toPass({ timeout: 8 * 60_000, intervals: [15_000] });
      await expect(page.getByText("Succeeded", { exact: true })).toBeVisible();
      await expect(page.getByText(/· 2 mentors, 3 mentees$/)).toBeVisible();
      await expect(
        page.getByRole("tab", { name: /^Matched \(/ }),
      ).toBeVisible();
      await expect(
        page.getByText("Could not load the matching results."),
      ).toHaveCount(0);
    });

    test("the result is edited under the lock, sent for approval and published", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId, memberId } = page.seed;

      await page.goto(`/mentorship-management/matching/${roundId}`);
      await expect(page.getByText("Succeeded", { exact: true })).toBeVisible({
        timeout: 20_000,
      });
      await expect(page.getByText(/^\d+–\d+ of \d+$/)).toBeVisible();
      await page.getByRole("button", { name: "Edit", exact: true }).click();
      await expect(
        page.getByRole("button", { name: "Stop editing" }),
      ).toBeVisible();

      // The one change: the member's row. Matched, its reason is rewritten;
      // left unmatched, they are given a mentor with a free slot.
      let row = resultRow(page, memberId);
      if ((await row.count()) === 0) {
        await page.getByRole("tab", { name: /^Unmatched \(/ }).click();
        row = resultRow(page, memberId);
        await expect(row).toHaveCount(1);
        await row.locator("button[aria-expanded]").click();
        await row.getByRole("combobox", { name: "Mentor" }).click();
        await page
          .getByRole("option", { name: /— [1-9]\d* of \d+ slots free/ })
          .first()
          .click();
      } else {
        await row.locator("button[aria-expanded]").click();
      }
      await row.getByLabel("Reason shown to the pair").fill(EDITED_REASON);
      await expect(page.getByText("Unsaved changes.")).toBeVisible();

      // Test runs a stub matcher that gives no reasons, and a pair without
      // one blocks publishing, so the other mentees get one too.
      await page.getByRole("tab", { name: /^Matched \(/ }).click();
      for (const name of ["Mentee B1", "Mentee B2"]) {
        const other = resultRow(page, idOf(page, name));
        if ((await other.count()) === 0) continue;
        const reason = other.getByLabel("Reason shown to the pair");
        if (!(await reason.isVisible())) {
          await other.locator("button[aria-expanded]").click();
        }
        if (!(await reason.inputValue()).trim()) {
          await reason.fill("E2E regression: reason written in the draft.");
        }
      }
      await page.getByRole("button", { name: "Save draft" }).click();
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toBeVisible();
      await expect(
        resultRow(page, memberId).getByText("Edited", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Problems to fix before publishing"),
      ).toHaveCount(0);

      const publish = page.getByRole("region", { name: "Publish approval" });
      await publish.getByRole("button", { name: "Request publishing" }).click();
      const dialog = page.getByRole("dialog");
      await pickReviewer(dialog, reviewer.account.userId);
      await dialog.getByLabel("Reason (optional)").fill("e2e regression");
      await dialog.getByRole("button", { name: "Send request" }).click();
      await expect(successToast(page, "Sent for approval.")).toBeVisible();
      await expect(publish).toContainText("Waiting for approval — sent to");
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toBeDisabled();

      await reviewer.goto(`/mentorship-management/matching/${roundId}`);
      const decide = reviewer.getByRole("region", { name: "Publish approval" });
      await decide
        .getByRole("button", { name: "Approve", exact: true })
        .click({ timeout: 20_000 });
      const confirm = reviewer.getByRole("dialog");
      await expect(
        confirm.getByRole("heading", { name: "Approve and publish" }),
      ).toBeVisible();
      await confirm
        .getByRole("button", { name: "Approve", exact: true })
        .click();
      await expect(
        successToast(reviewer, "Published. The pairs are in place."),
      ).toBeVisible();

      // The pairs are now real: in the Participants list and on both
      // detail pages.
      await openParticipants(page, { round: roundId, id: memberId });
      const listed = rowFor(page, memberId);
      await expect(listed).toContainText("matched");
      await expect(listed).toContainText(PARTNER);

      await openDetail(page, memberId, roundId);
      const section = roundSection(page, page.seed.roundName);
      await expect(section.getByText("Active", { exact: true })).toBeVisible();
      const partnerLink = section.getByRole("link", { name: PARTNER });
      await expect(partnerLink).toBeVisible();
      await partnerLink.click();
      await expect(page.getByText("Participation history")).toBeVisible({
        timeout: 20_000,
      });
      await expect(
        roundSection(page, page.seed.roundName).getByRole("link", {
          name: new RegExp(`· ID ${memberId}$`),
        }),
      ).toBeVisible();
    });

    test("the member sees their partner", async ({ as }) => {
      needFlagOn("matching-run");
      const member = await as("member");
      needSeed(member);

      const card = await openMemberDashboard(member);
      await expect(card.getByText("Mentor:")).toBeVisible();
      await expect(card.getByText(PARTNER)).toBeVisible();
      // The "View Matching Result" dialog belongs to the round card at the
      // top, which follows the open registration round that closes first.
      // The seeded rounds close later on purpose so real users keep the real
      // round there, so that dialog cannot show a seeded round's result.
    });

    test("the member logs a meeting, which the admin sees but cannot edit", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      test.skip(
        flag("manual-submit-meeting") !== true,
        "manual-submit-meeting is not declared on; members cannot log a meeting",
      );
      const member = await as("member");
      const page = await as("admin");
      needSeed(page);
      const { roundId, roundName, memberId } = page.seed;

      const card = await openMemberDashboard(member);
      const dialog = member.getByRole("dialog");
      // The earliest slot of yesterday, so it has ended whatever the time of
      // day in the member's time zone.
      const logYesterdaysFirstSlot = async () => {
        await card.getByRole("button", { name: "Manage Meetings" }).click();
        await dialog.getByRole("tab", { name: "Log Past Meeting" }).click();
        await pickDayBefore(member, dialog);
        await dialog
          .getByRole("combobox")
          .filter({ hasText: "Pick a start time" })
          .click();
        await member
          .getByRole("option", { name: "00:00", exact: true })
          .click();
        await dialog
          .getByRole("combobox")
          .filter({ hasText: "Pick an end time" })
          .click();
        await member
          .getByRole("option", { name: "00:30", exact: true })
          .click();
        await dialog.getByRole("button", { name: "Log Meeting" }).click();
      };
      await logYesterdaysFirstSlot();
      await expect(dialog).toBeHidden();

      // PUR-796: the same slot again is refused by the form, with the
      // server's message, before anything is sent.
      const posted = [];
      member.on("request", (req) => {
        if (req.method() === "POST" && /\/meeting/.test(req.url())) {
          posted.push(req.url());
        }
      });
      await logYesterdaysFirstSlot();
      await expect(
        dialog.getByText("This time slot already exists.", { exact: true }),
      ).toBeVisible();
      expect(posted).toEqual([]);
      await member.keyboard.press("Escape");
      await expect(dialog).toBeHidden();

      // A pair whose only meeting was logged by hand keeps a v1 log, and
      // admins edit only v2 logs (PairSection.jsx canEdit). Editing a log of
      // Google Meet meetings is 16-meeting-log-edit.
      await openDetail(page, memberId, roundId);
      const section = roundSection(page, roundName);
      await expect(section.getByText(/^Meetings 1\//)).toBeVisible();
      await expect(
        section.getByRole("button", { name: "Edit", exact: true }),
      ).toHaveCount(0);
    });
  },
);
