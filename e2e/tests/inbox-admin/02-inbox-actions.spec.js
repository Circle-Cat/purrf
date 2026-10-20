import { test, expect } from "../../fixtures.js";
import {
  ALIAS,
  inboxThreadReset,
  insertMessage,
  insertThread,
  needOps,
  openInbox,
  openThread,
  opsEmail,
  opsId,
  realThread,
  searchInbox,
  stamp,
  successToast,
  threadEvents,
  threadPanel,
  threadRow,
  threadRowButton,
} from "./helpers.js";
import { seedApplication } from "../recruiting/helpers.js";
import { idOf, nameOf } from "../mentorship/helpers.js";

// File, Transfer and Archive on the real "E2E inbox …" threads Yuji sent
// from the test mailbox (an inserted thread stands in while one has not
// arrived). None of these calls Gmail, and ASSIGNED, ARCHIVED, UNARCHIVED
// and MOVED notify nobody; only a Transfer of a thread that still needs a
// reply tells the target team (every holder of its permission, real staff
// included), which the guard refuses. Every test puts the threads back.
//
//   E2E inbox mentorship 1  filed to Mentee R1 in the seeded live round
//   E2E inbox recruiting 1  filed to Candidate R01's seeded application
//   E2E inbox inquiries 2   archived, brought back by new mail

/** A real thread by subject, else an inserted one like it. */
function threadFor(page, service, subject) {
  const real = realThread(subject);
  if (real) return { subject, threadId: real.threadId, real: true };
  const fake = `E2E fake ${stamp()} ${service}`;
  const threadId = insertThread({
    service,
    subject: fake,
    messages: [
      {
        from: opsEmail(opsId(page, "inbox")),
        to: ALIAS[service],
        text: "Stand-in for the real thread",
        minutesAgo: 10,
      },
    ],
  });
  return { subject: fake, threadId, real: false };
}

async function openOne(page, service, subject) {
  await openInbox(page, service);
  await searchInbox(page, subject);
  await openThread(page, subject);
  return threadPanel(page);
}

/** In the File dialog, pick someone else by user id. */
async function pickPerson(dialog, userId, name) {
  const change = dialog.getByRole("button", { name: "Change" });
  if (await change.isVisible()) await change.click();
  await dialog.getByLabel("Search people").fill(String(userId));
  await dialog
    .getByRole("button", { name: new RegExp(`${name}.*#${userId}$`) })
    .click();
  await expect(dialog.getByLabel("Selected person")).toContainText(
    `#${userId}`,
  );
}

test.describe("inbox: file, transfer, archive", { tag: "@inbox" }, () => {
  test.beforeEach(() => inboxThreadReset());
  test.afterEach(() => inboxThreadReset());

  test("a mentorship thread filed to a participant leaves the Inbox", async ({
    as,
  }) => {
    const page = await as("admin");
    needOps(page);
    const { roundId, roundName } = page.seed;
    const person = idOf(page, "Mentee R1");
    const thread = threadFor(page, "mentorship", "E2E inbox mentorship 1");
    const panel = await openOne(page, "mentorship", thread.subject);
    await panel.getByRole("button", { name: "File to participant" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "File to a participant" }),
    ).toBeVisible();
    await pickPerson(dialog, person, nameOf("Mentee R1"));
    const round = dialog.getByLabel("Round");
    await expect(round.locator(`option[value="${roundId}"]`)).toHaveText(
      new RegExp(`^${roundName}`),
    );
    await round.selectOption(String(roundId));
    await dialog.getByRole("button", { name: "File", exact: true }).click();
    await expect(successToast(page, "Filed to the participant.")).toBeVisible();
    await expect(dialog).toBeHidden();
    await expect(threadRowButton(page, thread.subject)).toHaveCount(0);

    expect(threadRow(thread.threadId)).toEqual({
      contextType: "activity",
      contextId: roundId,
      userId: person,
      archived: false,
    });
    expect(threadEvents(thread.threadId)).toEqual([
      { type: "inbox.assigned", notified: 0 },
    ]);
  });

  test("a recruiting thread filed to an application leaves the Inbox", async ({
    as,
  }) => {
    const page = await as("admin");
    needOps(page);
    const app = seedApplication(page, "Candidate R01");
    const thread = threadFor(page, "recruiting", "E2E inbox recruiting 1");
    const panel = await openOne(page, "recruiting", thread.subject);
    await panel.getByRole("button", { name: "File to application" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "File to an application" }),
    ).toBeVisible();
    await pickPerson(dialog, app.userId, "E2E Candidate R01");
    const select = dialog.getByLabel("Application");
    await expect(
      select.locator(`option[value="${app.applicationId}"]`),
    ).toContainText(`#${app.applicationId}`);
    await select.selectOption(String(app.applicationId));
    await dialog.getByRole("button", { name: "File", exact: true }).click();
    await expect(successToast(page, "Filed to the application.")).toBeVisible();
    await expect(threadRowButton(page, thread.subject)).toHaveCount(0);

    expect(threadRow(thread.threadId)).toEqual({
      contextType: "application",
      contextId: app.applicationId,
      userId: app.userId,
      archived: false,
    });
    expect(threadEvents(thread.threadId)).toEqual([
      { type: "inbox.assigned", notified: 0 },
    ]);
  });

  test("Archive hides a thread until they write again; Unarchive brings it back", async ({
    as,
  }) => {
    const page = await as("admin");
    needOps(page);
    const thread = threadFor(page, "inquiries", "E2E inbox inquiries 2");
    const panel = await openOne(page, "inquiries", thread.subject);
    await panel.getByRole("button", { name: "Archive" }).click();
    await expect(
      successToast(page, "Archived. It comes back when they write again."),
    ).toBeVisible();
    await expect(threadRowButton(page, thread.subject)).toHaveCount(0);
    expect(threadRow(thread.threadId).archived).toBe(true);

    await page.getByLabel("Show archived").check();
    const row = threadRowButton(page, thread.subject);
    await expect(row).toContainText("Archived");
    await openThread(page, thread.subject);
    await expect(panel.getByText("No reply needed")).toBeVisible();
    await panel.getByRole("button", { name: "Unarchive" }).click();
    await expect(panel.getByRole("button", { name: "Archive" })).toBeVisible();
    await expect(row).not.toContainText("Archived");
    expect(threadRow(thread.threadId).archived).toBe(false);

    // Archived again, then the sender writes in (a message row stands in
    // for the mail a Gmail push would store): it is back, needing a reply.
    await panel.getByRole("button", { name: "Archive" }).click();
    await expect(row).toContainText("Archived");
    insertMessage(thread.threadId, {
      from: "Yanpei Wang <wangyanpei76@gmail.com>",
      to: ALIAS.inquiries,
      text: "Writing again",
      // Half a minute ahead, so a clock skew between the backend and the
      // database cannot put it before archived_at.
      minutesAgo: -0.5,
    });
    await page.getByLabel("Show archived").uncheck();
    await expect(row).toBeVisible();
    await expect(row).toContainText("Needs reply");
    await expect(row).not.toContainText("Archived");
    expect(threadEvents(thread.threadId)).toEqual([
      { type: "inbox.archived", notified: 0 },
      { type: "inbox.unarchived", notified: 0 },
      { type: "inbox.archived", notified: 0 },
    ]);
  });

  test("a thread that needs no reply transfers to another service and tells nobody", async ({
    as,
  }) => {
    const page = await as("admin");
    const person = opsId(page, "inbox");
    const subject = `E2E fake ${stamp()} transfer`;
    const threadId = insertThread({
      service: "mentorship",
      subject,
      messages: [
        {
          from: opsEmail(person),
          to: ALIAS.mentorship,
          text: "Q",
          minutesAgo: 20,
        },
        {
          direction: "outbound",
          from: ALIAS.mentorship,
          to: opsEmail(person),
          text: "A",
          minutesAgo: 10,
        },
      ],
    });
    const panel = await openOne(page, "mentorship", subject);
    await expect(panel.getByText("No reply needed")).toBeVisible();
    await panel.getByLabel("Transfer to").selectOption("recruiting");
    await panel.getByRole("button", { name: "Transfer", exact: true }).click();
    await expect(
      panel.getByText(
        `Transferred from Mentorship; replies now sent from ${ALIAS.recruiting}`,
      ),
    ).toBeVisible();
    await expect(panel).toContainText(`From: ${ALIAS.recruiting}`);
    await expect(
      panel.getByRole("button", { name: "File to application" }),
    ).toBeVisible();
    expect(threadRow(threadId).contextType).toBe("recruiting_inbox");
    expect(threadEvents(threadId)).toEqual([
      { type: "inbox.moved", notified: 0 },
    ]);

    await openInbox(page, "recruiting");
    await searchInbox(page, subject);
    await expect(threadRowButton(page, subject)).toContainText(
      "Transferred from Mentorship",
    );
  });

  test("the guard refuses to transfer a thread that still needs a reply", async ({
    as,
  }) => {
    const page = await as("admin");
    const thread = threadFor(page, "mentorship", "E2E inbox mentorship 1");
    page.expectBlocked(/\/move: it needs a reply/);
    const panel = await openOne(page, "mentorship", thread.subject);
    await expect(panel.getByText("Needs reply", { exact: true })).toBeVisible();
    await panel.getByLabel("Transfer to").selectOption("inquiries");
    await panel.getByRole("button", { name: "Transfer", exact: true }).click();
    await expect(
      page.locator('[data-sonner-toast][data-type="error"]'),
    ).toBeVisible();
    expect(threadRow(thread.threadId).contextType).toBe("mentorship_inbox");
    expect(threadEvents(thread.threadId)).toEqual([]);
  });
});
