import { test, expect, settle } from "../../fixtures.js";
import { rowsOf } from "../../lib/seed.js";
import {
  callApi,
  candidateEmail,
  candidateName,
  openApplication,
  pickPerson,
  seedApplication,
  seedJob,
  successToast,
} from "./helpers.js";

// What the recruiter writes about an application, on the seeded board
// posting:
//   Candidate C1  a comment; an email to the candidate's alias (really sent,
//                 from the recruiting mailbox to the test mailbox), seen in
//                 the Emails tab and the timeline
//   Candidate B1  a comment @-mentioning e2e-reviewer, its assignee, which
//                 reaches the reviewer's notifications
//   Candidate I1  an interview booked with e2e-reviewer (a real Calendar
//                 invite to the candidate's alias, e2e-reviewer and
//                 e2e-admin), moved, then cancelled through the page
// Only what Purrf records is checked; nobody reads the mailbox.

/** A date a week from now, as the date input wants it. */
const nextWeek = () => {
  const d = new Date(Date.now() + 7 * 86_400_000);
  return d.toISOString().slice(0, 10);
};

const timelineOf = async (page) => {
  await page.getByRole("tab", { name: "Timeline", exact: true }).click();
  return page.getByRole("tabpanel");
};

test.describe("comments, email and interviews", { tag: "@recruiting" }, () => {
  test("a comment and an email to the candidate show on the application", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("admin");
    const c1 = seedApplication(page, "Candidate C1");
    const name = candidateName("Candidate C1");
    const said = `E2E regression comment ${Date.now()}`;

    await openApplication(page, c1.applicationId, name);
    await expect(
      page.getByText(candidateEmail(3), { exact: true }).first(),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Comments", exact: true }).click();
    await page.getByPlaceholder("Add a comment…").fill(said);
    await page.getByRole("button", { name: "Post", exact: true }).click();
    await expect(page.getByRole("tabpanel").getByText(said)).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page
        .getByRole("tabpanel")
        .getByRole("listitem")
        .filter({ hasText: said }),
      "the comment names its author",
    ).toContainText(/ — \S[^:]*: /);

    const subject = `E2E regression email ${Date.now()}`;
    await page.getByRole("tab", { name: "Emails", exact: true }).click();
    await page.getByRole("button", { name: "Send email" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Send email" }),
    ).toBeVisible();
    await expect(
      dialog.getByText("From: recruiting-test@circlecat.org"),
    ).toBeVisible();
    const to = dialog.getByRole("group", { name: "To" });
    await expect(to.getByText(candidateEmail(3))).toBeVisible();
    const box = to.getByRole("checkbox", {
      name: new RegExp(candidateEmail(3).replace(/[+.]/g, "\\$&")),
    });
    if (!(await box.isChecked())) await box.check();
    await dialog.getByLabel("Subject").fill(subject);
    await dialog
      .getByRole("textbox", { name: "Message" })
      .fill("E2E regression body. Please ignore.");
    await dialog.getByRole("button", { name: "Send", exact: true }).click();
    await expect(successToast(page, "Email sent.")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByRole("tabpanel").getByText(subject).first(),
    ).toBeVisible({
      timeout: 20_000,
    });

    await openApplication(page, c1.applicationId, name);
    const timeline = await timelineOf(page);
    await expect(timeline).toContainText(
      `Sent email "${subject}" to ${candidateEmail(3)}`,
    );
    expect(
      rowsOf(`SELECT count(*) FROM email_thread
              WHERE context_type = 'application' AND context_id = ${c1.applicationId}`)[0][0],
    ).toBe("1");
  });

  test("an @-mention of the assignee reaches their notifications", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const b1 = seedApplication(page, "Candidate B1");
    const said = `E2E regression mention ${Date.now()}`;
    await openApplication(
      page,
      b1.applicationId,
      candidateName("Candidate B1"),
    );

    const mentionable = await callApi(
      page,
      "GET",
      `/api/recruiting/applications/${b1.applicationId}/mentionable-users`,
    );
    expect(mentionable.status).toBe(200);
    expect(mentionable.json.data.map((u) => u.userId)).toContain(
      reviewer.account.userId,
    );

    const posted = await callApi(
      page,
      "POST",
      `/api/recruiting/applications/${b1.applicationId}/comments`,
      {
        body: `@[${reviewer.account.userId}] ${said}`,
      },
    );
    expect(posted.status, JSON.stringify(posted.json)).toBe(200);

    const comments = await callApi(
      page,
      "GET",
      `/api/recruiting/applications/${b1.applicationId}/comments`,
    );
    const mine = comments.json.data.find((c) => c.body.includes(said));
    expect(mine, "the comment is listed").toBeTruthy();
    expect((mine.mentions ?? []).map((m) => m.userId ?? m)).toContain(
      reviewer.account.userId,
    );

    // The notification carries the mention event's details, which name the
    // comment, and is resolved to the application's posting and applicant.
    await reviewer.goto("/");
    await settle(reviewer);
    await expect
      .poll(
        async () => {
          const bell = await callApi(
            reviewer,
            "GET",
            "/api/recruiting/notifications?limit=50",
          );
          expect(bell.status).toBe(200);
          return bell.json.data.notifications
            .filter(
              (n) =>
                n.eventType === "recruiting.mentioned" &&
                n.details?.commentId === posted.json.data.id,
            )
            .map((n) => ({
              mentionedIds: n.details.mentionedIds,
              jobTitle: n.jobTitle,
              applicantName: n.applicantName,
            }));
        },
        { timeout: 30_000 },
      )
      .toEqual([
        {
          mentionedIds: [reviewer.account.userId],
          jobTitle: seedJob(page, "board").title,
          applicantName: candidateName("Candidate B1"),
        },
      ]);
  });

  test("an interview is booked, moved and cancelled, and the calendar event is recorded", async ({
    as,
  }) => {
    test.setTimeout(150_000);
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const i1 = seedApplication(page, "Candidate I1");
    const name = candidateName("Candidate I1");

    await openApplication(page, i1.applicationId, name);
    const meeting = page.locator("main");
    await expect(
      meeting.getByText("Interview Meeting", { exact: true }),
    ).toBeVisible();
    await expect(
      meeting.getByText("Not scheduled", { exact: true }),
    ).toBeVisible();
    await meeting.getByRole("button", { name: "Schedule meeting" }).click();
    let dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Schedule interview meeting" }),
    ).toBeVisible();
    await pickPerson(page, "Interviewer", reviewer.account.email);
    await dialog.getByLabel("Date").fill(nextWeek());
    await dialog.getByLabel("Start time").fill("10:00");
    await dialog.getByRole("button", { name: "Schedule", exact: true }).click();
    await expect(successToast(page, "Interview scheduled.")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      meeting.getByText("Not scheduled", { exact: true }),
    ).toHaveCount(0);
    await expect(
      meeting.getByText(/^Interviewer: .*Scheduled by \S/),
    ).toBeVisible();

    const booked = rowsOf(
      `SELECT google_event_id, meet_link IS NOT NULL FROM application_interview WHERE application_id = ${i1.applicationId}`,
    );
    expect(booked).toHaveLength(1);
    expect(booked[0][0], "the calendar event id is stored").toMatch(/\S{6,}/);

    await meeting.getByRole("button", { name: "Edit", exact: true }).click();
    dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Edit interview meeting" }),
    ).toBeVisible();
    await expect(dialog.getByText(`Candidate: ${name}`)).toBeVisible();
    await dialog.getByLabel("Start time").fill("11:00");
    await dialog.getByRole("button", { name: "Save changes" }).click();
    await expect(successToast(page, "Interview updated.")).toBeVisible({
      timeout: 30_000,
    });
    expect(
      rowsOf(
        `SELECT google_event_id FROM application_interview WHERE application_id = ${i1.applicationId}`,
      )[0][0],
      "moving keeps the same event",
    ).toBe(booked[0][0]);

    await meeting.getByRole("button", { name: "Cancel", exact: true }).click();
    dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Cancel this interview meeting?" }),
    ).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel meeting" }).click();
    await expect(successToast(page, "Interview cancelled.")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      meeting.getByText("Not scheduled", { exact: true }),
    ).toBeVisible();
    expect(
      rowsOf(
        `SELECT count(*) FROM application_interview WHERE application_id = ${i1.applicationId}`,
      )[0][0],
    ).toBe("0");

    const timeline = await timelineOf(page);
    await expect(timeline).toContainText(
      "Scheduled the Behavioral interview meeting",
    );
    await expect(timeline).toContainText(
      "Rescheduled the Behavioral interview meeting",
    );
    await expect(timeline).toContainText(
      "Cancelled the Behavioral interview meeting",
    );
  });

  test("the audit overview breaks down the seeded posting and drops it when unticked", async ({
    as,
  }) => {
    const page = await as("admin");
    const job = seedJob(page, "board");
    await page.goto("/recruiting/audit");
    await expect(
      page.getByRole("heading", { name: "Recruiting Audit" }),
    ).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
    const chart = page.getByRole("img", {
      name: "Stage breakdown chart — Employment",
    });
    const box = page.getByRole("checkbox", { name: job.title, exact: true });
    await expect(box, "every posting is ticked by default").toBeChecked();
    await expect(chart.getByText(job.title, { exact: true })).toBeVisible();
    const answered = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/api/recruiting/audit/overview",
      { timeout: 20_000 },
    );
    await box.uncheck();
    expect((await answered).status()).toBe(200);
    await expect(chart.getByText(job.title, { exact: true })).toHaveCount(0);
  });
});
