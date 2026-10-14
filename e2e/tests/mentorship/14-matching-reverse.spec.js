import { test, expect, settle } from "../../fixtures.js";
import {
  idOf,
  nameOf,
  needFlagOn,
  needSeed,
  openParticipants,
  pickReviewer,
  rowFor,
  successToast,
} from "./helpers.js";

// One chain, run in order after 05 and stopped at the first failure: a run
// of the suite's own, its Unmatched tab and a hand assignment, then the
// publish request rejected, withdrawn, and finally approved, which clears
// the round's run so the next run of the suite finds nothing pending.
//   Mentor D1 (1 slot), Mentee D1, Mentee D2  the run; one mentee is left
//     unmatched and is given Mentor D1 by hand (over the slot), then put
//     back. Nobody else is picked, so the run touches no real person.

const RUN_GROUP = ["Mentor D1", "Mentee D1", "Mentee D2"];
const MENTEES = ["Mentee D1", "Mentee D2"];
const REASON = "E2E regression: reason written in the draft.";

function needMatching(page) {
  needFlagOn("matching-run");
  needSeed(page);
  test.skip(
    page.seed.matchingBusy,
    "someone else's run, draft, lock or publish request is on this round",
  );
}

/**
 * One person's row on the results page: the list item around the button
 * that opens it, found by the "ID <n>" on that button. (The Problems list
 * names people too, in plain lines.)
 */
const resultRow = (page, userId) =>
  page
    .getByRole("button", { name: new RegExp(`ID ${userId}\\b`) })
    .locator("xpath=..");

const publishRegion = (page) =>
  page.getByRole("region", { name: "Publish approval" });

async function openResults(page) {
  await page.goto(`/mentorship-management/matching/${page.seed.roundId}`);
  await expect(page.getByText("Succeeded", { exact: true })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText(/^\d+–\d+ of \d+$/)).toBeVisible();
  await settle(page);
}

/** The mentee the run left unmatched: its id and its Unmatched row. */
async function unmatchedMentee(page) {
  await page.getByRole("tab", { name: /^Unmatched \(/ }).click();
  await expect(page).toHaveURL(/tab=unmatched/);
  // Either seeded mentee's row; the list loads after the tab switches.
  const rows = MENTEES.map((name) => {
    const id = idOf(page, name);
    return { id, name, row: resultRow(page, id) };
  });
  await expect(rows[0].row.or(rows[1].row)).toHaveCount(1, {
    timeout: 20_000,
  });
  for (const found of rows) {
    if ((await found.row.count()) === 1) return found;
  }
  throw new Error("neither seeded mentee is on the Unmatched tab");
}

/** Ask e2e-reviewer to publish, from the results page. */
async function requestPublishing(page, reviewerId) {
  const publish = publishRegion(page);
  await publish.getByRole("button", { name: "Request publishing" }).click();
  const dialog = page.getByRole("dialog");
  await pickReviewer(dialog, reviewerId);
  await dialog.getByLabel("Reason (optional)").fill("e2e regression");
  await dialog.getByRole("button", { name: "Send request" }).click();
  await expect(successToast(page, "Sent for approval.")).toBeVisible();
  await expect(publish).toContainText("Waiting for approval — sent to");
}

test.describe(
  "matching: unmatched, hand assignment and the publish request's other ends",
  { tag: ["@mentorship", "@flag:matching-run"] },
  () => {
    test.describe.configure({ mode: "serial" });

    test("a run with one mentor slot for two mentees leaves one unmatched", async ({
      as,
    }) => {
      const page = await as("admin");
      needMatching(page);
      test.setTimeout(10 * 60_000);
      const { roundId, roundName } = page.seed;

      await openParticipants(page, {
        round: roundId,
        eligible: "1",
        sort: "user_id",
        order: "desc",
      });
      for (const name of RUN_GROUP) {
        await rowFor(page, idOf(page, name)).getByRole("checkbox").check();
      }
      await page.getByRole("button", { name: "Run matching · 3" }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toContainText("1 mentors and 2 mentees.");
      await dialog.getByRole("button", { name: "Run", exact: true }).click();
      await expect(page).toHaveURL(
        new RegExp(`/mentorship-management/matching/${roundId}$`),
      );

      await expect(async () => {
        await page.reload();
        await expect(
          page.getByText(/^(Succeeded|Failed|Unusable)$/),
        ).toBeVisible({ timeout: 10_000 });
      }).toPass({ timeout: 8 * 60_000, intervals: [15_000] });
      await expect(page.getByText("Succeeded", { exact: true })).toBeVisible();
      await expect(page.getByText(/· 1 mentors, 2 mentees$/)).toBeVisible();
      await expect(page.getByText(`Matching — ${roundName}`)).toBeVisible();
      await expect(
        page.getByRole("tab", { name: "Matched (1)", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("tab", { name: "Unmatched (1)" }),
      ).toBeVisible();
    });

    test("the Unmatched tab lists the mentee left over, with their profile", async ({
      as,
    }) => {
      const page = await as("admin");
      needMatching(page);
      await openResults(page);

      const { name, row } = await unmatchedMentee(page);
      await expect(page).toHaveURL(/tab=unmatched/);
      await expect(row).toContainText(nameOf(name));
      await expect(row).toContainText("Mentee");
      await expect(row).toContainText("No mentor");
      await row.locator("button[aria-expanded]").click();
      await expect(
        row.getByRole("region", { name: "Mentee profile" }),
      ).toContainText("E2E seed goal: land a software engineering role.");
      await expect(row.getByText("Matcher's notes")).toBeVisible();
      await expect(row.getByText("Other candidates")).toBeVisible();
      // Not editing: no mentor select.
      await expect(row.getByRole("combobox", { name: "Mentor" })).toHaveCount(
        0,
      );
    });

    test("a mentor given by hand over their slot is saved and blocks publishing until put back", async ({
      as,
    }) => {
      const page = await as("admin");
      needMatching(page);
      const mentor = idOf(page, "Mentor D1");
      await openResults(page);

      await page.getByRole("button", { name: "Edit", exact: true }).click();
      await expect(
        page.getByRole("button", { name: "Stop editing" }),
      ).toBeVisible();
      const { id, row } = await unmatchedMentee(page);
      await row.locator("button[aria-expanded]").click();
      await row.getByRole("combobox", { name: "Mentor" }).click();
      await page
        .getByRole("option", {
          name: new RegExp(
            `^${nameOf("Mentor D1")} \\(ID ${mentor}\\) — 0 of 1 slots free`,
          ),
        })
        .click();
      await expect(
        row.getByText("A matched mentee needs a reason."),
      ).toBeVisible();
      await row.getByLabel("Reason shown to the pair").fill(REASON);
      await expect(row).toContainText(`→ ${nameOf("Mentor D1")} ID ${mentor}`);
      await expect(page.getByText("Unsaved changes.")).toBeVisible();
      await page.getByRole("button", { name: "Save draft" }).click();
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toBeVisible();

      await expect(
        page.getByRole("region", { name: "Problems" }),
      ).toContainText(
        `${nameOf("Mentor D1")} (ID ${mentor}) is given 2 mentees but has 1 slot this run.`,
      );
      await expect(
        publishRegion(page).getByRole("button", { name: "Request publishing" }),
      ).toBeDisabled();
      // Saved with a mentor, the mentee moves to the Matched tab.
      await expect(
        page.getByRole("tab", { name: "Unmatched (0)", exact: true }),
      ).toBeVisible();
      await page.getByRole("tab", { name: "Matched (2)", exact: true }).click();
      const saved = resultRow(page, id);
      await expect(saved).toContainText(
        `→ ${nameOf("Mentor D1")} ID ${mentor}`,
      );
      await expect(saved.getByText("Edited", { exact: true })).toBeVisible();

      // Put the mentee back as the matcher left them, and give the matched
      // mentee a reason (the stub matcher on test writes none).
      await page.getByRole("button", { name: "Edit", exact: true }).click();
      await saved
        .getByRole("button", { name: new RegExp(`ID ${id}\\b`) })
        .click();
      await saved
        .getByRole("button", { name: "Revert to the matcher's result" })
        .click();
      await expect(
        saved.getByRole("button", { name: new RegExp(`ID ${id}\\b`) }),
      ).toContainText("No mentor");
      const other = MENTEES.map((n) => idOf(page, n)).find((m) => m !== id);
      const matched = resultRow(page, other);
      await matched.locator("button[aria-expanded]").click();
      const reason = matched.getByLabel("Reason shown to the pair");
      if (!(await reason.inputValue()).trim()) await reason.fill(REASON);
      await page.getByRole("button", { name: "Save draft" }).click();
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toBeVisible();
      await expect(page.getByRole("region", { name: "Problems" })).toHaveCount(
        0,
      );
      await expect(
        page.getByRole("tab", { name: "Unmatched (1)", exact: true }),
      ).toBeVisible();
      await expect(
        publishRegion(page).getByRole("button", { name: "Request publishing" }),
      ).toBeEnabled();
    });

    test("a rejected publish request needs a reason and unlocks the result", async ({
      as,
    }) => {
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needMatching(page);
      const comment = `e2e regression: not yet ${Date.now()}`;
      await openResults(page);
      await requestPublishing(page, reviewer.account.userId);
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toBeDisabled();

      await openResults(reviewer);
      await publishRegion(reviewer)
        .getByRole("button", { name: "Reject", exact: true })
        .click();
      const dialog = reviewer.getByRole("dialog");
      await expect(
        dialog.getByRole("heading", { name: "Reject publishing" }),
      ).toBeVisible();
      const reject = dialog.getByRole("button", {
        name: "Reject",
        exact: true,
      });
      await expect(reject, "a rejection needs a reason").toBeDisabled();
      await dialog.getByLabel("Reason", { exact: true }).fill(comment);
      await reject.click();
      await expect(
        successToast(reviewer, "Publishing rejected."),
      ).toBeVisible();

      await openResults(page);
      const publish = publishRegion(page);
      await expect(publish).toContainText(
        new RegExp(`Publishing was rejected by .+: ${comment}$`),
      );
      await expect(
        publish.getByRole("button", { name: "Request publishing" }),
      ).toBeEnabled();
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toBeEnabled();
    });

    test("a publish request taken back by its raiser leaves the result as it was", async ({
      as,
    }) => {
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needMatching(page);
      await openResults(page);
      await requestPublishing(page, reviewer.account.userId);

      const publish = publishRegion(page);
      // The raiser is not the reviewer, so cannot decide it.
      await expect(
        publish.getByRole("button", { name: "Approve", exact: true }),
      ).toHaveCount(0);
      await publish.getByRole("button", { name: "Withdraw" }).click();
      await expect(successToast(page, "Request withdrawn.")).toBeVisible();
      await expect(
        publish.getByRole("button", { name: "Request publishing" }),
      ).toBeEnabled();
      await expect(publish).not.toContainText("Waiting for approval");
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toBeEnabled();

      await openResults(reviewer);
      await expect(
        publishRegion(reviewer).getByRole("button", { name: "Approve" }),
      ).toHaveCount(0);
      await expect(page.getByText("Succeeded", { exact: true })).toBeVisible();
    });

    test("an approved publish creates the pair and clears the round's run", async ({
      as,
    }) => {
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needMatching(page);
      const { roundId, roundName } = page.seed;
      await openResults(page);
      const { id: left } = await unmatchedMentee(page);
      await requestPublishing(page, reviewer.account.userId);

      await openResults(reviewer);
      await publishRegion(reviewer)
        .getByRole("button", { name: "Approve", exact: true })
        .click();
      const confirm = reviewer.getByRole("dialog");
      await expect(confirm).toContainText("This creates 1 pairs");
      await confirm
        .getByRole("button", { name: "Approve", exact: true })
        .click();
      await expect(
        successToast(reviewer, "Published. The pairs are in place."),
      ).toBeVisible();

      await page.goto(`/mentorship-management/matching/${roundId}`);
      await expect(
        page.getByText(`No matching run for ${roundName} yet.`),
      ).toBeVisible({ timeout: 20_000 });

      await openParticipants(page, {
        round: roundId,
        q: "@e2e.purrf.test",
        sort: "user_id",
        order: "desc",
      });
      const matchedMentee = MENTEES.map((n) => idOf(page, n)).find(
        (id) => id !== left,
      );
      await expect(rowFor(page, matchedMentee)).toContainText("matched");
      await expect(rowFor(page, matchedMentee)).toContainText(
        `with ${nameOf("Mentor D1")}`,
      );
      // Publishing sets everyone in the run: left without a mentor is un_matched.
      await expect(rowFor(page, left)).toContainText("un_matched");
    });
  },
);
