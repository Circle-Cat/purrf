import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { expect } from "../../fixtures.js";
import { ENV } from "../../lib/env.js";
import { rowsOf } from "../../lib/seed.js";

export { callApi } from "../mentorship/helpers.js";
export { consoleErrors } from "../profile/helpers.js";

/**
 * Shared steps for the Dashboard and DataSearch specs. Locators come from
 * the English copy in frontend/src/pages/Dashboard.jsx and pages/DataSearch.
 * The activity data is real (synced into test's Redis), so every expected
 * value is taken from an API response, never written down.
 */

export const GROUPS = ["employees", "interns", "volunteers"];

/** A response to `METHOD /api/<path>` (exact path), within 60 s. */
export const apiResponse = (page, method, path) =>
  page.waitForResponse(
    (r) =>
      r.request().method() === method && new URL(r.url()).pathname === path,
    { timeout: 60_000 },
  );

/** Record every request to the given API paths, for "nothing was sent". */
export function recordCalls(page, pattern) {
  const calls = [];
  page.on("request", (r) => {
    const url = new URL(r.url());
    if (pattern.test(url.pathname)) calls.push(`${r.method()} ${url.pathname}`);
  });
  return calls;
}

/** The browser's today and a day `days` from it, as YYYY-MM-DD. */
export async function browserDay(page, days = 0) {
  return page.evaluate((d) => {
    const t = new Date();
    t.setDate(t.getDate() + d);
    const pad = (n) => String(n).padStart(2, "0");
    return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`;
  }, days);
}

/**
 * The layer's one whole-group summary (SIDE-EFFECTS.md, "Redis budget"):
 * the Dashboard's default groups over one week. A past week, since Gerrit
 * was retired in May 2026 and no recent week has a merged CL; in this one
 * several interns merged CLs, so every column has numbers to compare.
 */
export const weekQuery = () => ({
  startDate: "2026-05-04",
  endDate: "2026-05-10",
  includeTerminated: false,
  groups: ["interns", "employees"],
});

const WEEK_FILE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../.state/dashboard-week.json",
);

/**
 * Keep the week's rows for the other tests of this run (global setup deletes
 * the file at the start of every run), marked with the API they came from.
 */
export function rememberWeek(query, rows) {
  fs.mkdirSync(path.dirname(WEEK_FILE), { recursive: true });
  fs.writeFileSync(WEEK_FILE, JSON.stringify({ api: ENV.api, query, rows }));
}

/**
 * The rows of `weekQuery()`, kept by the Dashboard spec's first test. Never
 * asked for here: a second whole-group summary is exactly what the Redis
 * budget rules out, so without the kept rows this throws.
 */
export function weekRows() {
  let kept = null;
  try {
    kept = JSON.parse(fs.readFileSync(WEEK_FILE, "utf8"));
  } catch {
    // Not kept in this run.
  }
  if (
    kept?.api !== ENV.api ||
    !isDeepStrictEqual(kept.query, weekQuery()) ||
    !Array.isArray(kept.rows)
  ) {
    throw new Error(
      `no week summary kept for ${ENV.api} in ${WEEK_FILE}: dashboard/01's first test did not run in this run (or failed before its search)`,
    );
  }
  return kept.rows;
}

/**
 * Answer the page's `POST /api/summary` without Redis: with what
 * `rowsFor(body, week)` returns, `week()` giving `weekRows` (the default
 * answer), for the first `times` calls or all of them. Returns the bodies
 * it answered. If the answer cannot be made, the request gets a 500 naming
 * why, so the test fails on it at once instead of waiting on a route that
 * was never fulfilled.
 */
export async function stubSummary(
  page,
  { rowsFor = (_, week) => week(), times } = {},
) {
  const answered = [];
  await page.route(
    (url) => url.pathname === "/api/summary",
    async (route) => {
      let data;
      try {
        const body = route.request().postDataJSON();
        answered.push(body);
        data = await rowsFor(body, weekRows);
      } catch (error) {
        await route.fulfill({
          status: 500,
          json: { success: false, message: `stubSummary: ${error.message}` },
        });
        return;
      }
      await route.fulfill({
        json: { success: true, message: "Summary fetched successfully", data },
      });
    },
    times ? { times } : undefined,
  );
  return answered;
}

/** The ldaps in a `/api/microsoft/{status}/ldaps` answer, per group and status. */
export const ldapsOf = (data, group, status) =>
  Object.keys(data?.[group]?.[status] ?? {});

/** Every ldap in such an answer, once. */
export const allLdapsOf = (data) => [
  ...new Set(
    Object.values(data ?? {}).flatMap((byStatus) =>
      Object.values(byStatus ?? {}).flatMap((m) => Object.keys(m ?? {})),
    ),
  ),
];

/** The query string the pages use for the LDAP list. */
export const groupsQuery = (groups) =>
  groups.map((g) => `groups[]=${encodeURIComponent(g)}`).join("&");

/** Text of every body row of a table, cell by cell. */
export async function tableRows(table) {
  return table
    .locator("tbody tr")
    .evaluateAll((rows) =>
      rows.map((tr) =>
        [...tr.querySelectorAll("td")].map((td) => td.textContent.trim()),
      ),
    );
}

/** Header labels of a table. */
export async function tableHeaders(table) {
  return table
    .locator("thead th")
    .evaluateAll((ths) => ths.map((th) => th.textContent.trim()));
}

/**
 * Grant a permission to a test account for the length of `fn`, by a row
 * of our own that is deleted by id afterwards.
 */
export async function withGrant(userId, permission, fn) {
  if (!/^[a-z_.]+$/.test(permission)) throw new Error(`bad ${permission}`);
  const [[already]] = rowsOf(`
    SELECT count(*) FROM user_permissions
    WHERE user_id = ${Number(userId)} AND permission_name = '${permission}'
      AND revoked_timestamp IS NULL`);
  expect(already, `user ${userId} does not hold ${permission} yet`).toBe("0");
  const [[id]] = rowsOf(`
    INSERT INTO user_permissions (user_id, permission_name, granted_source)
    VALUES (${Number(userId)}, '${permission}', 'admin') RETURNING id`);
  try {
    return await fn();
  } finally {
    rowsOf(
      `DELETE FROM user_permissions WHERE id = ${Number(id)} RETURNING id`,
    );
  }
}
