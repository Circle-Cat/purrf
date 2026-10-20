import { test, expect, settle } from "../../fixtures.js";
import { rowsOf } from "../../lib/seed.js";
import {
  needRecruiting,
  openPosting,
  pickPerson,
  pickReviewer,
  successToast,
} from "./helpers.js";

// Postings the specs create are titled "E2E posting …" and owned by
// e2e-admin alone; e2e-reviewer and e2e-reviewer2 hold recruiting.job.approve
// and decide. cleanup.sql removes them with every review and event.
//   approve path  draft -> review -> published -> staged edit -> review ->
//                 applied; close requested and approved; reopen rejected
//   reject path   draft -> review -> reviewer changed -> rejected back to
//                 draft (with the comment shown) -> deleted

/** Fill the editor with a minimal posting and save it as a draft. */
async function createDraft(page, title) {
  await page.goto("/recruiting/postings");
  await expect(page.getByRole("heading", { name: "Job Postings" })).toBeVisible(
    { timeout: 20_000 },
  );
  await page.getByRole("button", { name: "New posting" }).click();
  await expect(
    page.getByRole("heading", { name: "New posting" }),
  ).toBeVisible();
  await settle(page);
  await page.getByLabel("Title", { exact: true }).fill(title);
  await page
    .getByLabel("Description", { exact: true })
    .fill("E2E regression posting, created by the suite.");
  await page.getByRole("combobox", { name: "Posting type" }).click();
  await page.getByRole("option", { name: "Employment", exact: true }).click();
  await pickPerson(page, "Add recruiter", page.account.email);
  await page.getByRole("checkbox", { name: "Recruiter Screening" }).check();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(successToast(page, "Posting created.")).toBeVisible();
  await expect(page).toHaveURL(/\/recruiting\/postings\/\d+$/);
  const id = Number(page.url().match(/\/postings\/(\d+)$/)[1]);
  await settle(page);
  return id;
}

/** Open a review request (submit, close, reopen) to the given reviewer. */
async function requestReview(page, button, reviewerId, message, done) {
  await page.getByRole("button", { name: button, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: button })).toBeVisible();
  await expect(
    dialog.locator(`option[value="${page.account.userId}"]`),
    "the submitter cannot pick themselves",
  ).toHaveCount(0);
  await pickReviewer(dialog, reviewerId);
  await dialog.getByLabel("Message (optional)").fill(message);
  await dialog.getByRole("button", { name: button, exact: true }).click();
  await expect(successToast(page, done)).toBeVisible();
  await expect(page).toHaveURL(/\/recruiting\/postings$/);
}

/** The reviewer's Pending approvals card on Job Postings. */
async function pendingApprovals(page) {
  await page.goto("/recruiting/postings");
  await expect(page.getByRole("heading", { name: "Job Postings" })).toBeVisible(
    { timeout: 20_000 },
  );
  await settle(page);
  return page.locator("section, div").filter({
    has: page.getByText("Pending approvals", { exact: true }),
  });
}

/** Approve or reject the review waiting on this reviewer on the posting page. */
async function decide(page, jobId, decision, comment) {
  await openPosting(page, jobId);
  await expect(page.getByText("Review decision:")).toBeVisible();
  if (decision === "approve") {
    await page.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(successToast(page, "Review approved.")).toBeVisible();
  } else {
    const reject = page.getByRole("button", { name: "Reject", exact: true });
    await expect(reject, "a rejection needs a comment").toBeDisabled();
    await page
      .getByPlaceholder("Rejection comment (required to reject)")
      .fill(comment);
    await reject.click();
    await expect(successToast(page, "Review rejected.")).toBeVisible();
  }
  await expect(page.getByText("Review decision:")).toHaveCount(0);
}

const statusBadge = (page, text) =>
  page
    .getByRole("heading", { level: 1 })
    .locator("..")
    .getByText(text, { exact: true });

test.describe("posting lifecycle", { tag: "@recruiting" }, () => {
  test("a draft is approved and published, a staged edit goes live after review, and close and reopen go through review", async ({
    as,
  }) => {
    test.setTimeout(240_000);
    const reviewer = await as("reviewer");
    const member = await as("member");
    const page = await as("admin");
    needRecruiting(page);
    const title = `E2E posting ${Date.now()}`;

    const id = await createDraft(page, title);
    await expect(statusBadge(page, "Draft")).toBeVisible();
    await requestReview(
      page,
      "Submit for review",
      reviewer.account.userId,
      "e2e regression: please publish",
      "Submitted for review.",
    );

    // Waiting on the reviewer: the author can no longer edit.
    await openPosting(page, id);
    await expect(
      page.getByText("Editing is locked until they approve or reject."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Edit", exact: true }),
    ).toHaveCount(0);

    const card = await pendingApprovals(reviewer);
    const row = card.getByRole("listitem").filter({ hasText: title });
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("e2e regression: please publish");
    await row.getByRole("button", { name: "Review" }).click();
    await expect(reviewer).toHaveURL(new RegExp(`/recruiting/postings/${id}$`));
    await decide(reviewer, id, "approve");
    await expect(statusBadge(reviewer, "Published")).toBeVisible();

    await member.goto("/recruiting/jobs");
    await expect(
      member.getByRole("button").filter({ hasText: title }),
      "a published posting is open to members",
    ).toHaveCount(1, { timeout: 20_000 });

    // An edit to a live posting is staged until a reviewer approves it.
    await openPosting(page, id);
    await page.getByRole("button", { name: "Edit", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Edit posting" }),
    ).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByLabel("Title", { exact: true })).toHaveValue(title);
    await page
      .getByLabel("Description", { exact: true })
      .fill("E2E regression posting, revised.");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(
      successToast(page, "Change staged, not yet live."),
    ).toBeVisible();
    await expect(
      page.getByText("Staged edit not submitted for review"),
    ).toBeVisible({
      timeout: 20_000,
    });
    await member.goto(`/recruiting/jobs/${id}`);
    await expect(
      member.getByText("E2E regression posting, created by the suite."),
    ).toBeVisible({
      timeout: 20_000,
    });
    await openPosting(page, id);
    await requestReview(
      page,
      "Submit for review",
      reviewer.account.userId,
      "e2e regression: revision",
      "Submitted for review.",
    );
    await decide(reviewer, id, "approve");
    await member.goto(`/recruiting/jobs/${id}`);
    await expect(
      member.getByText("E2E regression posting, revised."),
    ).toBeVisible({
      timeout: 20_000,
    });

    // Close, approved: no longer open; reopen, rejected: stays closed.
    await openPosting(page, id);
    await requestReview(
      page,
      "Request close",
      reviewer.account.userId,
      "e2e regression: close",
      "Close requested.",
    );
    await decide(reviewer, id, "approve");
    await expect(statusBadge(reviewer, "Closed")).toBeVisible();
    await member.goto("/recruiting/jobs");
    await settle(member);
    await expect(
      member.getByRole("button").filter({ hasText: title }),
    ).toHaveCount(0);

    await openPosting(page, id);
    await expect(
      page.getByText("Published postings cannot be deleted"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Delete", exact: true }),
    ).toHaveCount(0);
    await requestReview(
      page,
      "Request reopen",
      reviewer.account.userId,
      "e2e regression: reopen",
      "Reopen requested.",
    );
    await decide(reviewer, id, "reject", "e2e regression: stays closed");
    await expect(statusBadge(reviewer, "Closed")).toBeVisible();

    await openPosting(page, id);
    await page.getByRole("tab", { name: "Review history" }).click();
    const history = page.getByRole("tabpanel");
    for (const line of [
      "created this posting as a draft",
      "approved the review — posting published",
      "approved the revision — changes published",
      "approved the close request — posting closed",
      'rejected the reopen request: "e2e regression: stays closed" — posting stays closed',
    ]) {
      await expect(history.getByText(line, { exact: false })).toHaveCount(1);
    }
  });

  test("a review moved to another reviewer is rejected back to draft with its comment, and the draft is deleted", async ({
    as,
  }) => {
    test.setTimeout(180_000);
    const second = await as("reviewer2");
    const reviewer = await as("reviewer");
    const page = await as("admin");
    needRecruiting(page);
    const title = `E2E posting ${Date.now()}`;

    const id = await createDraft(page, title);
    await requestReview(
      page,
      "Submit for review",
      reviewer.account.userId,
      "e2e regression: reject me",
      "Submitted for review.",
    );

    await openPosting(page, id);
    await expect(
      page.getByText(`Assigned reviewer: User ${reviewer.account.userId}`),
    ).toBeVisible();
    await page.getByRole("button", { name: "Change reviewer" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Change reviewer" }),
    ).toBeVisible();
    await expect(
      dialog.locator(`option[value="${reviewer.account.userId}"]`),
      "the current reviewer is left out",
    ).toHaveCount(0);
    await pickReviewer(dialog, second.account.userId);
    await dialog.getByRole("button", { name: "Reassign", exact: true }).click();
    await expect(successToast(page, "Reviewer changed.")).toBeVisible();
    await expect(
      page.getByText(`Assigned reviewer: User ${second.account.userId}`),
    ).toBeVisible();

    // The first reviewer no longer decides it.
    await openPosting(reviewer, id);
    await expect(reviewer.getByText("Review decision:")).toHaveCount(0);

    await decide(second, id, "reject", "e2e regression: not yet");
    await openPosting(page, id);
    await expect(statusBadge(page, "Draft")).toBeVisible();
    await expect(page.getByText("e2e regression: not yet")).toBeVisible();

    // PUR-789: its reviews, events and their notifications go with it. Taken
    // before the delete, since a notification is tied to the posting only
    // through its event.
    const reviewsOf = () =>
      rowsOf(`
        SELECT request_id FROM approval_request
        WHERE action = 'job_review' AND target_type = 'job'
          AND target_id = '${id}'`).flat();
    const eventIds = rowsOf(`
      SELECT event_id FROM event
      WHERE subject_type = 'job' AND subject_id = ${id}`).flat();
    expect(reviewsOf(), "the posting has its reviews").toHaveLength(1);
    expect(eventIds.length, "the posting has events").toBeGreaterThan(0);
    const notificationIds = rowsOf(`
      SELECT notification_id FROM notification
      WHERE event_id IN (${eventIds.join(",")})`).flat();
    expect(
      notificationIds.length,
      "its events notified someone",
    ).toBeGreaterThan(0);

    await page.getByRole("button", { name: "Delete", exact: true }).click();
    const confirm = page.getByRole("dialog");
    await expect(
      confirm.getByRole("heading", { name: "Delete this posting?" }),
    ).toBeVisible();
    await confirm.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(page).toHaveURL(/\/recruiting\/postings$/, {
      timeout: 20_000,
    });
    await settle(page);
    await expect(
      page.getByRole("button").filter({ hasText: title }),
    ).toHaveCount(0);

    expect(reviewsOf(), "its reviews are deleted").toEqual([]);
    expect(
      rowsOf(`
        SELECT event_id FROM event
        WHERE (subject_type = 'job' AND subject_id = ${id})
           OR event_id IN (${eventIds.join(",")})`),
      "its events are deleted",
    ).toEqual([]);
    expect(
      rowsOf(`
        SELECT notification_id FROM notification
        WHERE notification_id IN (${notificationIds.join(",")})`),
      "the notifications about them are deleted",
    ).toEqual([]);
  });

  // PUR-787: a reviewer without a name is shown as "User <id>", with the
  // submitter's controls.
  test("the submitter sees who reviews a posting and can withdraw it", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    const page = await as("admin");
    needRecruiting(page);
    const id = await createDraft(page, `E2E posting ${Date.now()}`);
    await requestReview(
      page,
      "Submit for review",
      reviewer.account.userId,
      "e2e regression: withdraw me",
      "Submitted for review.",
    );
    await openPosting(page, id);
    await expect(
      page.getByText(`Assigned reviewer: User ${reviewer.account.userId}`),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Change reviewer" }),
    ).toBeEnabled();
    const withdraw = page.getByRole("button", {
      name: "Withdraw",
      exact: true,
    });
    await expect(withdraw).toBeEnabled();
    await withdraw.click();
    await expect(successToast(page, "Review withdrawn.")).toBeVisible();
    await expect(statusBadge(page, "Draft")).toBeVisible();
    await expect(page.getByText(/^Assigned reviewer: /)).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Submit for review" }),
    ).toBeEnabled();
  });
});
