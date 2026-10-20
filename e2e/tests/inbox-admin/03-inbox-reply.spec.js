import { test, expect } from "../../fixtures.js";
import {
  ALIAS,
  inboxThreadReset,
  insertMessage,
  needOps,
  openInbox,
  openThread,
  realThread,
  rowsOf,
  searchInbox,
  threadEvents,
  threadPanel,
  threadRow,
} from "./helpers.js";

// A real reply, on the real thread Yuji sent from the test mailbox to the
// mentorship alias: Purrf sends it through Gmail as mentorship-test@ to the
// thread's newest human sender, which the guard checks is the test mailbox
// before letting the call out. Once answered the thread needs no reply, so
// transferring it tells nobody. The thread is put back afterwards; the
// reply stays in both mailboxes.

const SUBJECT = "E2E inbox mentorship 1";
const MAILBOX = "wangyanpei76@gmail.com";

test.describe("inbox: reply", { tag: "@inbox" }, () => {
  test.beforeEach(() => inboxThreadReset());
  test.afterEach(() => inboxThreadReset());

  test("a reply goes out from the service alias, after newer mail is read first; then the thread transfers quietly", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("admin");
    needOps(page);
    const real = realThread(SUBJECT);
    test.skip(!real, `the real thread ${SUBJECT} has not arrived`);

    await openInbox(page, "mentorship");
    await searchInbox(page, SUBJECT);
    await openThread(page, SUBJECT);
    const panel = threadPanel(page);
    await expect(panel.getByText("Needs reply", { exact: true })).toBeVisible();
    await expect(panel).toContainText(`From: ${ALIAS.mentorship}`);
    await expect(panel).toContainText(`To: ${MAILBOX}`);

    // Mail that lands while the reply is being written: the send is refused
    // with 409 and nothing goes out until it has been seen.
    insertMessage(real.threadId, {
      from: `Yanpei Wang <${MAILBOX}>`,
      to: ALIAS.mentorship,
      text: "One more thing before you answer",
      minutesAgo: 0,
    });
    page.expectApiError({
      method: "POST",
      path: new RegExp(`^/api/inbox/threads/${real.threadId}/reply$`),
      status: 409,
    });
    const text = `E2E reply ${Date.now()}`;
    await panel.getByLabel("Reply").fill(text);
    await panel.getByRole("button", { name: "Send reply" }).click();
    await expect(
      panel
        .getByRole("status")
        .filter({ hasText: "Not sent: this thread has new messages" }),
    ).toBeVisible();
    await expect(panel).toContainText("One more thing before you answer");
    expect(
      rowsOf(
        `SELECT count(*) FROM email_message WHERE thread_id = ${real.threadId} AND direction = 'outbound'`,
      )[0][0],
    ).toBe("0");

    await expect(panel.getByLabel("Reply")).toHaveValue(text);
    await panel.getByRole("button", { name: "Send reply" }).click();
    await expect(panel.getByText("No reply needed")).toBeVisible({
      timeout: 30_000,
    });
    await expect(panel.getByLabel("Reply")).toHaveValue("");
    const sent = panel.getByRole("listitem", { name: /^Message / }).filter({
      hasText: text,
    });
    await expect(sent).toContainText("Sent");
    await expect(sent).toContainText(`From${ALIAS.mentorship}`);
    await expect(sent).toContainText(`To${MAILBOX}`);
    const [[from, to, by]] = rowsOf(`
      SELECT from_address, to_addresses, sent_by_user_id FROM email_message
      WHERE thread_id = ${real.threadId} AND direction = 'outbound'`);
    expect({ from, to, by: Number(by) }).toEqual({
      from: ALIAS.mentorship,
      to: MAILBOX,
      by: page.account.userId,
    });

    await panel.getByLabel("Transfer to").selectOption("inquiries");
    await panel.getByRole("button", { name: "Transfer", exact: true }).click();
    await expect(
      panel.getByText(
        `Transferred from Mentorship; replies now sent from ${ALIAS.inquiries}`,
      ),
    ).toBeVisible();
    expect(threadRow(real.threadId).contextType).toBe("inquiries_inbox");
    expect(threadEvents(real.threadId)).toEqual([
      { type: "inbox.moved", notified: 0 },
    ]);
  });
});
