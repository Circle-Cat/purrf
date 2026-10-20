import { randomBytes } from "node:crypto";
import { test, expect, settle } from "../../fixtures.js";
import { inboxThreadReset, rowsOf, suiteRealThreads } from "../../lib/seed.js";

export { callApi, successToast } from "../mentorship/helpers.js";
export { inboxThreadReset, rowsOf };

/**
 * Shared steps for the Inbox and account console specs. Locators come from
 * the English copy in frontend/src/pages/Inbox, AdminAccounts and
 * AdminPermissions.
 */

/** Skip a write test when global setup did not seed the ops people. */
export function needOps(page) {
  test.skip(
    !page.seed?.inboxAdmin,
    "not seeded (needs E2E_DATABASE_URL and the admin and member tokens, on test)",
  );
  return page.seed.inboxAdmin.people;
}

/** A seeded ops person's user id: "deactivate", "block", "search", … */
export const opsId = (page, key) => {
  const id = needOps(page)[key];
  if (!id) throw new Error(`seed has no ops person "${key}"`);
  return id;
};

/** Ops people are "E2E Ops <Key>". */
export const opsName = (key) =>
  `E2E Ops ${key.charAt(0).toUpperCase()}${key.slice(1)}`;

/** The ops person's primary alias. */
export const opsEmail = (id) => `wangyanpei76+e2e-ops-${id - 990300}@gmail.com`;

/** The test environment's service aliases (terraform/environments/test). */
export const ALIAS = {
  mentorship: "mentorship-test@circlecat.org",
  recruiting: "recruiting-test@circlecat.org",
  inquiries: "inquiries-test@circlecat.org",
};

const CONTEXT = {
  mentorship: "mentorship_inbox",
  recruiting: "recruiting_inbox",
  inquiries: "inquiries_inbox",
};

export const stamp = () =>
  new Date().toISOString().slice(5, 19).replace(/\D/g, "");

const lit = (value) =>
  value == null ? "NULL" : `'${String(value).replace(/'/g, "''")}'`;

/**
 * Insert an Inbox thread straight into the database, as if Gmail had
 * brought it: gmail ids start "e2e-", so it is the suite's and no sync or
 * Gmail call ever reaches it. Messages are oldest first, each
 * {direction, from, to, html, text, minutesAgo, kind}. Returns the thread id.
 */
export function insertThread({ service, subject, messages }) {
  const gmailId = `e2e-${randomBytes(6).toString("hex")}`;
  const [[threadId]] = rowsOf(`
    INSERT INTO email_thread (gmail_thread_id, subject, context_type, created_at)
    VALUES (${lit(gmailId)}, ${lit(subject)}, ${lit(CONTEXT[service])},
            now() - interval '${Math.max(...messages.map((m) => m.minutesAgo ?? 0)) + 1} minutes')
    RETURNING thread_id`);
  messages.forEach((m, i) =>
    insertMessage(Number(threadId), m, `${gmailId}-${i}`),
  );
  return Number(threadId);
}

/** Add one message to a thread; an inbound one is human mail. */
export function insertMessage(threadId, m, gmailMessageId) {
  const id = gmailMessageId ?? `e2e-${randomBytes(6).toString("hex")}`;
  const at = `now() - interval '${m.minutesAgo ?? 0} minutes'`;
  const inbound = m.direction !== "outbound";
  rowsOf(`
    INSERT INTO email_message (thread_id, gmail_message_id, direction,
      from_address, to_addresses, subject, body_html, body_text, snippet,
      gmail_internal_date, created_at, inbound_kind)
    VALUES (${threadId}, ${lit(id)}, ${lit(inbound ? "inbound" : "outbound")},
      ${lit(m.from)}, ${lit(m.to)}, ${lit(m.subject ?? null)},
      ${lit(m.html ?? null)}, ${lit(m.text ?? null)},
      ${lit((m.text ?? "").slice(0, 100) || null)},
      ${inbound ? at : "NULL"}, ${at}, ${inbound ? `'${m.kind ?? "human"}'` : "NULL"})
    RETURNING message_id`);
}

/** A thread's row as the database holds it now. */
export function threadRow(threadId) {
  const [row] = rowsOf(`
    SELECT context_type, COALESCE(context_id::text, ''), COALESCE(user_id::text, ''),
           archived_at IS NOT NULL
    FROM email_thread WHERE thread_id = ${threadId}`);
  if (!row) return null;
  return {
    contextType: row[0],
    contextId: row[1] ? Number(row[1]) : null,
    userId: row[2] ? Number(row[2]) : null,
    archived: row[3] === "t",
  };
}

/** Event types recorded on a thread, oldest first, with how many people each notified. */
export function threadEvents(threadId) {
  return rowsOf(`
    SELECT e.event_type, (SELECT count(*) FROM notification n WHERE n.event_id = e.event_id)
    FROM event e
    WHERE e.subject_type = 'email_thread' AND e.subject_id = ${threadId}
      AND e.actor_id IS NOT NULL
    ORDER BY e.event_id`).map(([type, notified]) => ({
    type,
    notified: Number(notified),
  }));
}

/**
 * One of the real threads Yuji sent from the test mailbox ("E2E inbox
 * mentorship 1", …), or null while it has not arrived; the test then uses
 * an inserted thread or skips.
 */
export const realThread = (subject) => suiteRealThreads()[subject] ?? null;

/**
 * Open the Inbox, optionally on one service, and wait for its list.
 * Returns the body of the list response the page rendered from.
 */
export async function openInbox(page, service) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/inbox/threads",
    { timeout: 30_000 },
  );
  await page.goto(service ? `/inbox?service=${service}` : "/inbox");
  const body = await (await loaded).json();
  await expect(
    page.getByRole("heading", { name: "Inbox", level: 1 }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
  return body;
}

/** Narrow the list with the search box and wait for the answer. */
export async function searchInbox(page, term) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/inbox/threads" &&
      new URL(r.url()).searchParams.get("q") === term,
    { timeout: 15_000 },
  );
  await page.getByLabel("Search threads").fill(term);
  await loaded;
}

/** The list row of a thread, by subject. */
export const threadRowButton = (page, subject) =>
  page.getByRole("button", { name: `Open thread ${subject}`, exact: true });

/** The open thread's panel. */
export const threadPanel = (page) =>
  page.getByRole("region", { name: "Thread", exact: true });

/** Open a thread from the list and wait for its detail. */
export async function openThread(page, subject) {
  await threadRowButton(page, subject).click();
  await expect(
    threadPanel(page).getByRole("heading", { level: 2, name: subject }),
  ).toBeVisible({ timeout: 15_000 });
}

/** Open one account on the console and wait for its header. */
export async function openAccount(page, userId, heading) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/admin/accounts" &&
      new URL(r.url()).searchParams.get("user_id") === String(userId),
    { timeout: 30_000 },
  );
  await page.goto(`/admin/accounts?user_id=${userId}`);
  await loaded;
  await expect(
    page.getByRole("heading", { level: 1, name: heading }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
}

/** One user row's state as the database holds it. */
export function userState(userId) {
  const [[active, blocked]] = rowsOf(
    `SELECT is_active, is_blocked FROM users WHERE user_id = ${userId}`,
  );
  return { active: active === "t", blocked: blocked === "t" };
}

/** Who was notified of each event about a user, oldest first. */
export function userEventRecipients(userId, since) {
  return rowsOf(`
    SELECT e.event_type,
      COALESCE((SELECT string_agg(n.user_id::text, ',' ORDER BY n.user_id)
                  FROM notification n WHERE n.event_id = e.event_id), '')
    FROM event e
    WHERE ((e.subject_type = 'user' AND e.subject_id = ${userId})
           OR e.details ->> 'requestId' IN (
             SELECT request_id::text FROM approval_request
             WHERE target_type = 'user' AND target_id = '${userId}'))
      AND e.event_id > ${since}
    ORDER BY e.event_id`).map(([type, to]) => ({
    type,
    to: to ? to.split(",").map(Number) : [],
  }));
}

/** The newest event id, to read only what a test recorded after it. */
export const lastEventId = () =>
  Number(rowsOf("SELECT COALESCE(max(event_id), 0) FROM event")[0][0]);
