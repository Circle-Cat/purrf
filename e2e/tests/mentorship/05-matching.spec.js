import { test, expect, settle } from "../../fixtures.js";
import { flag } from "../../lib/flags.js";
import {
  idOf,
  needFlagOn,
  needSeed,
  openDetail,
  openParticipants,
  pickReviewer,
  roundSection,
  rowFor,
  successToast,
} from "./helpers.js";

// One chain, run in order and stopped at the first failure: the guard lets
// the results be edited and published only after the suite itself started a
// run in the round, and the member's meetings need the published pair.
//   Mentor B1, Mentor B2, Mentee B1, Mentee B2, e2e-member  the run, the
//     published pairs; e2e-member also logs a meeting and sends feedback.
// Nobody else is picked, so the run touches no real person.

const RUN_GROUP = ["Mentor B1", "Mentor B2", "Mentee B1", "Mentee B2"];
const PARTNER = /E2E Mentor B[12]/;
const EDITED_REASON = "E2E regression: reason edited in the draft.";

function needMatching(page) {
  needSeed(page);
  test.skip(
    page.seed.matchingBusy,
    "someone else's run, draft, lock or publish request is on this round",
  );
}

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

/** One mentee's row on the results page, by the "ID <n>" in it. */
const resultRow = (page, userId) =>
  page.locator("li").filter({ hasText: new RegExp(`ID ${userId}\\b`) });

/** The member's dashboard, with the round in progress shown in the card. */
async function openMemberDashboard(member) {
  await member.goto("/dashboard/me");
  const card = member
    .locator('[data-slot="card"]')
    .filter({ hasText: "Mentorship Participation" });
  await expect(card).toBeVisible({ timeout: 20_000 });
  await expect(card.getByText("Loading participation data...")).toBeHidden({
    timeout: 20_000,
  });
  const roundPicker = card.getByRole("combobox");
  if (!(await roundPicker.textContent())?.includes(member.seed.roundName)) {
    await roundPicker.click();
    await member
      .getByRole("option", { name: new RegExp(`^${member.seed.roundName}`) })
      .click();
  }
  await settle(member);
  return card;
}

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
      needMatching(page);
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
      needMatching(page);
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
      needMatching(member);

      const card = await openMemberDashboard(member);
      await expect(card.getByText("Mentor:")).toBeVisible();
      await expect(card.getByText(PARTNER)).toBeVisible();

      await member
        .getByRole("button", { name: "View Matching Result" })
        .click();
      const dialog = member.getByRole("dialog");
      await expect(dialog.getByText("Congratulations!")).toBeVisible();
      await expect(dialog.getByText(PARTNER)).toBeVisible();
      await member.keyboard.press("Escape");
    });

    test("the member logs a meeting and the admin corrects it", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      test.skip(
        flag("manual-submit-meeting") !== true,
        "manual-submit-meeting is not declared on; members cannot log a meeting",
      );
      const member = await as("member");
      const page = await as("admin");
      needMatching(page);
      const { roundId, roundName, memberId } = page.seed;

      const card = await openMemberDashboard(member);
      await card.getByRole("button", { name: "Manage Meetings" }).click();
      const dialog = member.getByRole("dialog");
      await dialog.getByRole("tab", { name: "Log Past Meeting" }).click();
      // Earliest slots of today, so never in the future (except in the
      // first half hour after midnight in the member's time zone).
      await dialog
        .getByRole("combobox")
        .filter({ hasText: "Pick a start time" })
        .click();
      await member.getByRole("option", { name: "00:00", exact: true }).click();
      await dialog
        .getByRole("combobox")
        .filter({ hasText: "Pick an end time" })
        .click();
      await member.getByRole("option", { name: "00:30", exact: true }).click();
      await dialog.getByRole("button", { name: "Log Meeting" }).click();
      await expect(dialog).toBeHidden();

      // Opening the detail page is also what lets the guard allow the edit.
      await openDetail(page, memberId, roundId);
      const section = roundSection(page, roundName);
      await expect(section.getByText(/^Meetings 1\//)).toBeVisible();
      // Admins can edit a log only in a v2 round (PairSection.jsx canEdit);
      // in an older round the member's part is all there is to check.
      const edit = section.getByRole("button", { name: "Edit", exact: true });
      if ((await edit.count()) === 0) {
        test.info().annotations.push({
          type: "not checked",
          description: `${roundName} keeps a v1 meeting log, which admins cannot edit`,
        });
        return;
      }
      await edit.click();
      await section.getByRole("combobox", { name: "Complete Status" }).click();
      await page
        .getByRole("option", { name: "Incomplete", exact: true })
        .click();
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
      await expect(section.getByText(/^Meetings 0\//)).toBeVisible();
    });

    test("the member's feedback shows on the round's feedback page", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const member = await as("member");
      const page = await as("admin");
      needMatching(page);
      const { roundId, memberId } = page.seed;

      // The dashboard offers feedback only while the round's window is open.
      const card = await openMemberDashboard(member);
      const open = card.getByRole("button", {
        name: /^(Submit|Edit) Feedback$/,
      });
      test.skip(
        (await open.count()) === 0,
        "the round's feedback window is not open",
      );
      await open.click();
      const dialog = member.getByRole("dialog");
      const said = `E2E regression feedback ${Date.now()}`;
      await dialog
        .getByPlaceholder("Share what you found most valuable...")
        .fill(said);
      await dialog.getByRole("radio", { name: "5", exact: true }).check();
      await dialog.getByRole("radio", { name: "Excellent" }).check();
      await dialog
        .getByRole("button", { name: /^(Submit|Save Changes)$/ })
        .click();
      await expect(
        successToast(member, /^Feedback (Submitted|Updated)/),
      ).toBeVisible();

      await page.goto(`/mentorship-management/rounds/${roundId}/feedback`);
      const row = page
        .locator("table tbody tr")
        .filter({ hasText: new RegExp(`\\b${memberId}\\b`) });
      await expect(row).toContainText(said, { timeout: 20_000 });
    });
  },
);
