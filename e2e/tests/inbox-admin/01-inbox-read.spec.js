import { test, expect } from "../../fixtures.js";
import {
  ALIAS,
  inboxThreadReset,
  insertThread,
  needOps,
  openInbox,
  openThread,
  opsEmail,
  opsId,
  realThread,
  searchInbox,
  stamp,
  threadPanel,
  threadRowButton,
} from "./helpers.js";

// Reading the Inbox as e2e-admin, who holds all three services. Threads are
// inserted into the database (gmail ids "e2e-…"), so nothing here reaches
// Gmail except the attachment download, which reads one of the real "E2E
// inbox" threads from the test mailbox when it has arrived.
//
//   mentorship  from Ops Inbox's primary alias, waiting for a reply
//   recruiting  from an address nobody holds, waiting for a reply
//   inquiries   from Ops Search's alternative alias, already answered

test.describe("inbox: reading", { tag: "@inbox" }, () => {
  test.afterEach(() => inboxThreadReset());

  test("lists every service's threads, filters by service, needs reply, person and search", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("admin");
    needOps(page);
    const tag = `E2E fake ${stamp()}`;
    const inboxPerson = opsId(page, "inbox");
    const subjects = {
      mentorship: `${tag} mentorship`,
      recruiting: `${tag} recruiting`,
      inquiries: `${tag} inquiries`,
    };
    insertThread({
      service: "mentorship",
      subject: subjects.mentorship,
      messages: [
        {
          from: `E2E Ops Inbox <${opsEmail(inboxPerson)}>`,
          to: ALIAS.mentorship,
          text: "When does the next round open?",
          minutesAgo: 30,
        },
      ],
    });
    insertThread({
      service: "recruiting",
      subject: subjects.recruiting,
      messages: [
        {
          from: "nobody-e2e@e2e.purrf.test",
          to: ALIAS.recruiting,
          text: "Is the position still open?",
          minutesAgo: 20,
        },
      ],
    });
    insertThread({
      service: "inquiries",
      subject: subjects.inquiries,
      messages: [
        {
          from: "wangyanpei76+e2e-ops-3-alt@gmail.com",
          to: ALIAS.inquiries,
          text: "A general question",
          minutesAgo: 15,
        },
        {
          direction: "outbound",
          from: ALIAS.inquiries,
          to: "wangyanpei76+e2e-ops-3-alt@gmail.com",
          text: "Answered",
          minutesAgo: 10,
        },
      ],
    });

    const listed = await openInbox(page);
    const services = page.getByRole("group", { name: "Services" });
    for (const label of ["All", "Mentorship", "Recruiting", "Inquiries"]) {
      await expect(
        services.getByRole("button", { name: new RegExp(`^${label}`) }),
      ).toBeVisible();
    }
    // The header badge is the sum of the per-service counts in the list
    // response the page loaded.
    const total = listed.data.services.reduce((n, s) => n + s.needsReply, 0);
    await expect(
      page.getByText(`Needs reply: ${total}`, { exact: true }),
    ).toBeVisible();

    await searchInbox(page, tag);
    for (const subject of Object.values(subjects)) {
      await expect(threadRowButton(page, subject)).toBeVisible();
    }
    const mentorshipRow = threadRowButton(page, subjects.mentorship);
    await expect(mentorshipRow).toContainText(
      `E2E Ops Inbox · #${inboxPerson}`,
    );
    await expect(mentorshipRow).toContainText("Needs reply");
    const recruitingRow = threadRowButton(page, subjects.recruiting);
    await expect(recruitingRow).toContainText("nobody-e2e@e2e.purrf.test");
    await expect(recruitingRow).toContainText("No matching user");
    const inquiriesRow = threadRowButton(page, subjects.inquiries);
    await expect(inquiriesRow).toContainText(
      `E2E Ops Search · #${opsId(page, "search")}`,
    );
    await expect(inquiriesRow).not.toContainText("Needs reply");

    await services.getByRole("button", { name: /^Mentorship/ }).click();
    await expect(page).toHaveURL(/service=mentorship/);
    await expect(threadRowButton(page, subjects.mentorship)).toBeVisible();
    await expect(threadRowButton(page, subjects.recruiting)).toHaveCount(0);
    await expect(threadRowButton(page, subjects.inquiries)).toHaveCount(0);
    await services.getByRole("button", { name: /^Inquiries/ }).click();
    await expect(threadRowButton(page, subjects.inquiries)).toBeVisible();
    await expect(threadRowButton(page, subjects.mentorship)).toHaveCount(0);
    await services.getByRole("button", { name: /^All/ }).click();

    await page
      .getByRole("group", { name: "Filters" })
      .getByRole("button", { name: /^Needs reply/ })
      .click();
    await expect(threadRowButton(page, subjects.mentorship)).toBeVisible();
    await expect(threadRowButton(page, subjects.recruiting)).toBeVisible();
    await expect(threadRowButton(page, subjects.inquiries)).toHaveCount(0);
    await page
      .getByRole("group", { name: "Filters" })
      .getByRole("button", { name: /^Needs reply/ })
      .click();

    await page.getByLabel("User ID").fill(String(inboxPerson));
    await expect(threadRowButton(page, subjects.recruiting)).toHaveCount(0);
    await expect(threadRowButton(page, subjects.mentorship)).toBeVisible();
    await page.getByLabel("User ID").fill("");

    // Search covers the person's name, the sender address and the subject.
    await searchInbox(page, "e2e-ops-3-alt");
    await expect(threadRowButton(page, subjects.inquiries)).toBeVisible();
    await expect(threadRowButton(page, subjects.mentorship)).toHaveCount(0);
    await searchInbox(page, "nobody-e2e@");
    await expect(threadRowButton(page, subjects.recruiting)).toBeVisible();
    await expect(threadRowButton(page, subjects.inquiries)).toHaveCount(0);
  });

  test("a thread's detail shows who wrote, from which alias a reply goes, and HTML rendered inert", async ({
    as,
  }) => {
    const page = await as("admin");
    const inboxPerson = opsId(page, "inbox");
    const subject = `E2E fake ${stamp()} html`;
    insertThread({
      service: "mentorship",
      subject,
      messages: [
        {
          from: `E2E Ops Inbox <${opsEmail(inboxPerson)}>`,
          to: ALIAS.mentorship,
          text: "plain part",
          html: [
            "<p id='e2e-body'>Hello from the e2e suite</p>",
            "<script>window.__e2eXss = 'script'</script>",
            "<img src='x' onerror=\"window.__e2eXss = 'onerror'\">",
            "<style>main, nav { display: none !important }</style>",
            "<div id='e2e-overlay' style='position:fixed;inset:0;z-index:9999;background:red'>overlay</div>",
            "<a id='e2e-js-link' href=\"javascript:window.__e2eXss='link'\">link</a>",
          ].join(""),
          minutesAgo: 40,
        },
        {
          direction: "outbound",
          from: ALIAS.mentorship,
          to: opsEmail(inboxPerson),
          text: "Plain text answer\nsecond line",
          minutesAgo: 35,
        },
        {
          from: opsEmail(inboxPerson),
          to: ALIAS.mentorship,
          text: "Thanks, one more question",
          minutesAgo: 30,
        },
      ],
    });

    await openInbox(page);
    await searchInbox(page, subject);
    await openThread(page, subject);
    const panel = threadPanel(page);
    await expect(panel).toContainText(`E2E Ops Inbox · #${inboxPerson}`);
    await expect(panel.getByText("Matched by primary email")).toBeVisible();
    await expect(panel.getByText("Needs reply", { exact: true })).toBeVisible();
    await expect(
      panel.getByRole("button", { name: "File to participant" }),
    ).toBeEnabled();
    await expect(panel.getByRole("button", { name: "Archive" })).toBeEnabled();
    await expect(panel).toContainText(`From: ${ALIAS.mentorship}`);
    await expect(panel).toContainText(`To: ${opsEmail(inboxPerson)}`);
    await expect(panel.getByText("Received", { exact: true })).toHaveCount(2);
    await expect(panel.getByText("Sent", { exact: true })).toHaveCount(1);
    await expect(panel).toContainText("Plain text answer");

    await expect(page.locator("#e2e-body")).toHaveText(
      "Hello from the e2e suite",
    );
    const body = page.locator("#e2e-body").locator("..");
    await expect(body.locator("script, style")).toHaveCount(0);
    expect(await body.locator("img").getAttribute("onerror")).toBeNull();
    expect(await page.locator("#e2e-js-link").getAttribute("href")).toBeNull();
    expect(await page.evaluate(() => window.__e2eXss)).toBeUndefined();
    await expect(
      page.getByRole("heading", { name: "Inbox", level: 1 }),
      "the message's <style> did not reach the page",
    ).toBeVisible();
    // A fixed-position block stays inside the message box instead of
    // covering the page, so the actions stay clickable.
    const box = await body.boundingBox();
    const overlay = await page.locator("#e2e-overlay").boundingBox();
    expect(overlay.y + overlay.height).toBeLessThanOrEqual(
      box.y + box.height + 1,
    );
    expect(overlay.width).toBeLessThanOrEqual(box.width + 1);
    await panel.getByRole("button", { name: "Archive" }).click({ trial: true });
  });

  test("an inquiries thread cannot be filed and an attachment downloads", async ({
    as,
  }) => {
    const page = await as("admin");
    needOps(page);
    const real = realThread("E2E inbox inquiries 1");
    test.skip(!real, "the real thread E2E inbox inquiries 1 has not arrived");
    await openInbox(page, "inquiries");
    await searchInbox(page, "E2E inbox inquiries 1");
    await openThread(page, "E2E inbox inquiries 1");
    const panel = threadPanel(page);
    await expect(panel.getByRole("button", { name: /^File to/ })).toHaveCount(
      0,
    );
    await expect(panel).toContainText(`From: ${ALIAS.inquiries}`);
    const link = panel
      .getByRole("list", { name: "Attachments" })
      .getByRole("link")
      .first();
    await expect(link).toBeVisible();
    const name = (await link.innerText()).split("\n")[0].trim();
    const href = await link.getAttribute("href");
    const res = await page.request.get(href);
    expect(res.status(), href).toBe(200);
    expect((await res.body()).length).toBeGreaterThan(0);
    expect(res.headers()["content-disposition"] ?? "").toMatch(/^attachment/);
    expect(name.length).toBeGreaterThan(0);
  });
});
