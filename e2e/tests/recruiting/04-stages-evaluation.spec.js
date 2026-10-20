import { test, expect, settle } from "../../fixtures.js";
import { rowsOf } from "../../lib/seed.js";
import {
  callApi,
  candidateName,
  openApplication,
  pickPersonRadio,
  seedApplication,
  successToast,
} from "./helpers.js";

// Stage work on the seeded board posting, as its recruiter (e2e-admin), with
// e2e-reviewer as the interviewer:
//   Candidate A1  assigned in Recruiter screening, evaluated (a second
//                 confirm is refused), advanced to Behavioral, then rejected
//   Candidate O1  Behavioral session 2 with no evaluation: advanced to Offer
//                 past the reminder, then hired (an employment posting, so
//                 no onboarding training is assigned)

const stageBadge = (page, name, stage) =>
  page
    .getByRole("heading", { level: 1, name })
    .locator("..")
    .getByText(stage, { exact: true });

/** Fill the rubric: every pass/fail as Pass, every score as 4, every note. */
async function fillRubric(page) {
  const notes = page.getByPlaceholder("Notes");
  for (let i = 0; i < (await notes.count()); i += 1) {
    await notes.nth(i).fill("E2E regression notes");
  }
  const passes = page.getByRole("button", { name: "Pass", exact: true });
  for (let i = 0; i < (await passes.count()); i += 1)
    await passes.nth(i).click();
  const fours = page.getByRole("button", { name: "4", exact: true });
  for (let i = 0; i < (await fours.count()); i += 1) await fours.nth(i).click();
}

test.describe("stages and evaluations", { tag: "@recruiting" }, () => {
  test("an assigned interviewer evaluates once, and the recruiter advances and then rejects", async ({
    as,
  }) => {
    test.setTimeout(180_000);
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const a1 = seedApplication(page, "Candidate A1");
    const name = candidateName("Candidate A1");
    const reviewerEmail = reviewer.account.email;

    await openApplication(page, a1.applicationId, name);
    await expect(stageBadge(page, name, "Recruiter screening")).toBeVisible();
    await page.getByRole("button", { name: "Reassign", exact: true }).click();
    const reassign = page.getByRole("dialog");
    await expect(
      reassign.getByRole("heading", { name: "Reassign" }),
    ).toBeVisible();
    await expect(
      reassign.getByRole("button", { name: "Confirm reassign" }),
    ).toBeDisabled();
    await pickPersonRadio(reassign, reviewerEmail);
    await reassign.getByRole("button", { name: "Confirm reassign" }).click();
    await expect(successToast(page, "Reassigned.")).toBeVisible();
    await expect(
      page.getByText(`Assigned to: User ${reviewer.account.userId}`, {
        exact: true,
      }),
    ).toBeVisible();
    expect(
      rowsOf(
        `SELECT assignee_id FROM application_assignment WHERE application_id = ${a1.applicationId} AND stage = 'recruiter_screening'`,
      ),
    ).toEqual([[String(reviewer.account.userId)]]);

    // The interviewer finds it on My Interview Evaluations.
    await reviewer.goto("/recruiting/my-evaluations");
    const row = reviewer.getByRole("link").filter({ hasText: name });
    await expect(row).toHaveCount(1, { timeout: 20_000 });
    await expect(row).toContainText("Recruiter screening — Session 1");
    await expect(row).toContainText("Pending");
    await row.click();
    await expect(reviewer).toHaveURL(
      new RegExp(
        `/recruiting/applications/${a1.applicationId}\\?mode=evaluate$`,
      ),
    );
    await expect(reviewer.getByRole("heading", { level: 1, name })).toBeVisible(
      {
        timeout: 20_000,
      },
    );
    await settle(reviewer);
    await fillRubric(reviewer);
    await reviewer.getByRole("button", { name: "Save draft" }).click();
    await expect(successToast(reviewer, "Draft saved.")).toBeVisible();
    await reviewer.getByRole("button", { name: "Confirm & Submit" }).click();
    const confirm = reviewer.getByRole("dialog");
    await expect(
      confirm.getByText("This cannot be edited after submitting."),
    ).toBeVisible();
    await confirm.getByRole("button", { name: "Submit", exact: true }).click();
    await expect(successToast(reviewer, "Evaluation submitted.")).toBeVisible();
    await settle(reviewer);
    await expect(
      reviewer.getByRole("button", { name: "Confirm & Submit" }),
      "a confirmed evaluation cannot be submitted again from the page",
    ).toHaveCount(0);

    // Nor straight through the API.
    for (const status of [400, 403, 409]) {
      reviewer.expectApiError({
        method: "PUT",
        path: new RegExp(
          `^/api/recruiting/applications/${a1.applicationId}/evaluation$`,
        ),
        status,
      });
    }
    const again = await callApi(
      reviewer,
      "PUT",
      `/api/recruiting/applications/${a1.applicationId}/evaluation`,
      { responses: { overall: { value: 1 } }, confirm: true },
    );
    expect([400, 403, 409], JSON.stringify(again.json)).toContain(again.status);
    expect(
      rowsOf(
        `SELECT count(*), bool_and(is_confirmed) FROM evaluation WHERE application_id = ${a1.applicationId}`,
      )[0],
    ).toEqual(["1", "t"]);

    await reviewer.goto("/recruiting/my-evaluations");
    await expect(
      reviewer.getByRole("link").filter({ hasText: name }),
    ).toContainText("Confirmed", { timeout: 20_000 });

    // The recruiter sees the evaluation and advances to Behavioral.
    await openApplication(page, a1.applicationId, name);
    await page.getByRole("tab", { name: "Evaluations", exact: true }).click();
    await expect(page.getByRole("tabpanel")).toContainText(
      /Background Fitness|Overall/,
    );
    // Behavioral picks its interviewer on the meeting card, so the advance
    // asks nothing.
    await page.getByRole("button", { name: "Advance to Behavioral" }).click();
    await expect(successToast(page, "Advanced to Behavioral.")).toBeVisible();
    await expect(stageBadge(page, name, "Behavioral")).toBeVisible();

    await page.getByRole("button", { name: "Reject", exact: true }).click();
    const reject = page.getByRole("dialog");
    await expect(
      reject.getByRole("button", { name: "Confirm reject" }),
    ).toBeDisabled();
    await reject.getByRole("combobox", { name: "Rejection reason" }).click();
    await page.getByRole("option").first().click();
    await reject
      .getByPlaceholder("Note (optional)")
      .fill("e2e regression: not a fit");
    await reject.getByRole("button", { name: "Confirm reject" }).click();
    await expect(successToast(page, "Application rejected.")).toBeVisible();
    await expect(stageBadge(page, name, "Rejected")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^Advance to / }),
    ).toHaveCount(0);
  });

  test("the recruiter advances past the missing-evaluation reminder to Offer, then hires", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("admin");
    const o1 = seedApplication(page, "Candidate O1");
    const name = candidateName("Candidate O1");

    await openApplication(page, o1.applicationId, name);
    await expect(stageBadge(page, name, "Behavioral")).toBeVisible();
    await page.getByRole("button", { name: "Advance to Offer" }).click();
    const remind = page.getByRole("dialog");
    await expect(
      remind.getByRole("heading", { name: "No evaluation recorded" }),
    ).toBeVisible();
    // Offer and Hired take no assignee and O1 has no meeting booked, so
    // neither advance asks for a confirmation.
    await remind.getByRole("button", { name: "Advance anyway" }).click();
    await expect(successToast(page, "Advanced to Offer.")).toBeVisible();
    await expect(stageBadge(page, name, "Offer")).toBeVisible();

    await page.getByRole("button", { name: "Advance to Hired" }).click();
    await expect(successToast(page, "Advanced to Hired.")).toBeVisible();
    await expect(stageBadge(page, name, "Hired")).toBeVisible();

    await page.getByRole("tab", { name: "Timeline", exact: true }).click();
    // An entry reads "<time> — <description>, by <actor>".
    await expect(
      page.getByRole("tabpanel").getByRole("listitem").filter({
        hasText:
          "— Advanced from Behavioral to Offer (no evaluation recorded), by ",
      }),
    ).toHaveCount(1);
    expect(
      rowsOf(
        `SELECT count(*) FROM training WHERE user_id = ${o1.userId}`,
      )[0][0],
      "hiring onto an employment posting assigns no onboarding training",
    ).toBe("0");
  });

  // PUR-787: an assignee without a name is shown as "User <id>". Seeded
  // Candidate B1 is assigned to e2e-reviewer.
  test("the recruiter sees who an application is assigned to", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const b1 = seedApplication(page, "Candidate B1");
    await openApplication(
      page,
      b1.applicationId,
      candidateName("Candidate B1"),
    );
    await expect(
      page.getByText(`Assigned to: User ${reviewer.account.userId}`, {
        exact: true,
      }),
    ).toBeVisible();
  });
});
