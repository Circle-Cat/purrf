import { test, expect, settle } from "../../fixtures.js";
import { rowsOf } from "../../lib/seed.js";

export { callApi, needFlagOff } from "../mentorship/helpers.js";
export { rowsOf };

/**
 * Shared steps for the leave specs. Locators come from the English copy in
 * frontend/src/pages/Leave and PersonalDashboard/components/TimeOffCard.jsx.
 * Every seeded request carries a unique reason ("E2E R1 approve me"), which
 * is how a row is found on screen.
 */

/** Skip a test when global setup did not seed the leave data. */
export function needLeaveSeed(page) {
  test.skip(
    !page.seed?.leave,
    "leave not seeded (needs E2E_DATABASE_URL and the admin, member and reviewer tokens, on test)",
  );
  return page.seed.leave;
}

/** A seeded request's id by key ("R1", "M2", …). */
export const requestId = (page, key) => {
  const id = page.seed.leave.requests[key];
  if (!Number.isInteger(id)) throw new Error(`no seeded leave request ${key}`);
  return id;
};

/** A leave seed person's id by last name ("Leave Approve"). */
export const personId = (page, lastName) => {
  const id = page.seed.leave.people[lastName];
  if (!Number.isInteger(id))
    throw new Error(`no leave seed person ${lastName}`);
  return id;
};

/** Today in Beijing, the leave calendar's day, as YYYY-MM-DD. */
export const beijingToday = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());

/** This year in Beijing, the year the leave pages open on. */
export const beijingYear = () => Number(beijingToday().slice(0, 4));

/** A YYYY-MM-DD date `days` away from another. */
export const shiftDate = (iso, days) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
};

/**
 * The Time off card's three figures for one person, from the database, as
 * the server works them out (leave_request_service.standing): Pending is
 * the paid hours of undecided requests, Available the ledger balance less
 * that, Used this Beijing year's deductions. Each as "28.00".
 */
export function standingOf(userId) {
  const id = Number(userId);
  const [[balance, pending, deducted]] = rowsOf(`
    SELECT
      (SELECT COALESCE(sum(hours), 0) FROM leave_ledger WHERE user_id = ${id}),
      (SELECT COALESCE(sum(hours), 0) FROM leave_request
       WHERE user_id = ${id} AND type = 'paid' AND status = 'pending'),
      (SELECT COALESCE(sum(hours), 0) FROM leave_ledger
       WHERE user_id = ${id} AND entry_type = 'leave_deduction'
         AND extract(year FROM effective_date) = ${beijingYear()})`);
  return {
    available: (Number(balance) - Number(pending)).toFixed(2),
    pending: Number(pending).toFixed(2),
    used: (-Number(deducted)).toFixed(2),
  };
}

/**
 * One year's company holidays as the pages show them
 * (leave_calendar_segments.group_into_segments): runs of consecutive days
 * under one name that agree on exchangeable. [{name, days}], by date.
 */
export function segmentsOf(year) {
  const segments = [];
  let last = null;
  for (const [date, name, exchangeable] of rowsOf(`
    SELECT date, name, is_exchangeable FROM leave_holiday
    WHERE year = ${Number(year)} ORDER BY date`)) {
    const open = segments.at(-1);
    if (
      last &&
      open.name === name &&
      open.exchangeable === exchangeable &&
      shiftDate(last, 1) === date
    ) {
      open.days += 1;
    } else {
      segments.push({ name, exchangeable, days: 1 });
    }
    last = date;
  }
  return segments.map(({ name, days }) => ({ name, days }));
}

/** A request and its approval row, from the database. */
export function storedRequest(id) {
  const [row] = rowsOf(`
    SELECT r.status, r.is_overdraft, a.status, a.decided_by, a.decision_comment
    FROM leave_request r
    LEFT JOIN approval_request a
      ON a.action = 'leave_approval' AND a.target_id = r.leave_request_id::text
    WHERE r.leave_request_id = ${Number(id)}
    ORDER BY a.request_id DESC LIMIT 1`);
  if (!row) return null;
  const [status, overdraft, approval, decidedBy, comment] = row;
  return {
    status,
    isOverdraft: overdraft === "t",
    approval: approval || null,
    decidedBy: decidedBy ? Number(decidedBy) : null,
    comment: comment || null,
  };
}

/** Ledger rows written from one request: [entry_type, hours, date, created_by]. */
export const ledgerOfRequest = (id) =>
  rowsOf(`
    SELECT entry_type, hours, effective_date, created_by FROM leave_ledger
    WHERE source_request_id = ${Number(id)} ORDER BY leave_ledger_id`);

/** Every ledger row of a person: [entry_type, hours, date, note, created_by]. */
export const ledgerOf = (userId) =>
  rowsOf(`
    SELECT entry_type, hours, effective_date, COALESCE(note, ''), COALESCE(created_by::text, '')
    FROM leave_ledger WHERE user_id = ${Number(userId)}
    ORDER BY effective_date DESC, leave_ledger_id DESC`);

/**
 * The events about one request and who each notifies:
 * [{type, decision, actor, recipients: [user ids]}].
 */
export const eventsOf = (id) =>
  rowsOf(`
    SELECT e.event_type, COALESCE(e.details->>'decision', ''), COALESCE(e.actor_id::text, ''),
           COALESCE((SELECT string_agg(n.user_id::text, ',' ORDER BY n.user_id)
                     FROM notification n WHERE n.event_id = e.event_id), '')
    FROM event e
    WHERE e.subject_type = 'leave_request' AND e.subject_id = ${Number(id)}
    ORDER BY e.event_id`).map(([type, decision, actor, recipients]) => ({
    type,
    decision,
    actor: actor ? Number(actor) : null,
    recipients: recipients ? recipients.split(",").map(Number) : [],
  }));

/** How many requests one person has filed. */
export const requestCount = (userId) =>
  Number(
    rowsOf(
      `SELECT count(*) FROM leave_request WHERE user_id = ${Number(userId)}`,
    )[0][0],
  );

/** Requests waiting on one approver. */
export const pendingFor = (approverId) =>
  Number(
    rowsOf(`
    SELECT count(*) FROM leave_request
    WHERE approver_user_id = ${Number(approverId)} AND status = 'pending'`)[0][0],
  );

/** Record every write the page sends to the API, as "METHOD path". */
export function recordWrites(page) {
  const writes = [];
  page.on("request", (req) => {
    if (["GET", "HEAD", "OPTIONS"].includes(req.method())) return;
    const url = new URL(req.url());
    if (url.pathname.startsWith("/api/"))
      writes.push(`${req.method()} ${url.pathname}`);
  });
  return writes;
}

const answered = (page, path) =>
  page.waitForResponse(
    (r) => r.request().method() === "GET" && new URL(r.url()).pathname === path,
    { timeout: 30_000 },
  );

/** The dashboard's Time off card. */
export const timeOffCard = (page) =>
  page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText("Time off", { exact: true }) });

/** Open the Personal Dashboard and wait for its leave reads. */
export async function openDashboard(page) {
  const standing = answered(page, "/api/leave/me");
  const approvals = answered(page, "/api/leave/requests/approvals");
  await page.goto("/dashboard/me");
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible({
    timeout: 20_000,
  });
  await Promise.all([standing, approvals]);
  await settle(page);
}

/** One figure of the Time off card ("Available"), as "28.00h" and its hint. */
export const stat = (card, label) =>
  card
    .locator("div.min-w-0")
    .filter({ has: card.page().getByText(label, { exact: true }) });

/** Open Leave Approvals and wait for the list. */
export async function openApprovals(page) {
  const loaded = answered(page, "/api/leave/requests/approvals");
  await page.goto("/leave/approvals");
  await loaded;
  await expect(
    page.getByRole("heading", { name: "Leave Approvals" }),
  ).toBeVisible();
  await expect(page.getByText("Loading…")).toHaveCount(0);
}

/** A section of Leave Approvals ("Waiting on you", "Decided"). */
export const section = (page, title) =>
  page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText(title, { exact: true }) });

/** The list row carrying a request's reason. */
export const rowWith = (scope, reason) =>
  scope.locator("li").filter({ hasText: reason });

/** Open My Leave and wait for the list. */
export async function openMyLeave(page) {
  const loaded = answered(page, "/api/leave/me");
  await page.goto("/leave/requests");
  await loaded;
  await expect(page.getByRole("heading", { name: "My Leave" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Loading…")).toHaveCount(0);
}

/** Open Leave administration on one tab ("Balances", "Yearly setup"). */
export async function openAdmin(page, tab) {
  await page.goto("/leave/admin");
  await expect(
    page.getByRole("heading", { name: "Leave administration" }),
  ).toBeVisible({ timeout: 20_000 });
  if (tab !== "Balances") await page.getByRole("tab", { name: tab }).click();
  await expect(page.getByText("Loading…")).toHaveCount(0);
}
