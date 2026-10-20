import { test, expect } from "../../fixtures.js";
import { databaseUrl } from "../../lib/seed.js";
import { flag } from "../../lib/flags.js";
import {
  GROUPS,
  apiResponse,
  callApi,
  groupsQuery,
  recordCalls,
  stubSummary,
  withGrant,
} from "./helpers.js";

// Who reaches the Dashboard and DataSearch. The Dashboard and its one call,
// POST /api/summary, need dashboard.activity_summary.read; DataSearch and
// every call behind it, the LDAP list included (PUR-777), need
// internal_activity.read. Only e2e-admin holds either; the last three tests
// give e2e-readonly one of them for the length of the test.
//
// Redis is read per member (SIDE-EFFECTS.md, "Redis budget"): the calls name
// one made-up ldap, since an empty list means every intern and employee; a
// summary, which can only ask for whole groups, is sent with its end before
// its start, which the server refuses past the permission check and before
// reading any activity; and the pages' own summaries are answered by
// stubSummary.

const DASHBOARD = "dashboard.activity_summary.read";
const ACTIVITY = "internal_activity.read";

const link = (page, name) => page.getByRole("link", { name, exact: true });

/** Each call behind the two pages, with a body that would be valid. */
const day = "2026-01-01";
const NOBODY = "e2e-nobody";
const SUMMARY_CALL = [
  "POST",
  "/api/summary",
  {
    startDate: day,
    endDate: "2025-12-31",
    groups: ["employees"],
    includeTerminated: false,
  },
];
const ACTIVITY_CALLS = [
  ["GET", `/api/microsoft/active/ldaps?${groupsQuery(GROUPS)}`],
  ["GET", `/api/microsoft/all/ldaps?${groupsQuery(GROUPS)}`],
  ["GET", "/api/microsoft/chat/topics"],
  ["GET", "/api/google/chat/spaces"],
  ["GET", "/api/jira/projects"],
  ["GET", "/api/gerrit/projects"],
  ["GET", "/api/calendar/calendars"],
  [
    "POST",
    "/api/microsoft/chat/count",
    { ldaps: [NOBODY], startDate: day, endDate: day },
  ],
  [
    "POST",
    "/api/google/chat/count",
    { ldaps: [NOBODY], spaceIds: [], startDate: day, endDate: day },
  ],
  [
    "POST",
    "/api/jira/brief",
    {
      ldaps: [NOBODY],
      projectIds: [],
      statusList: ["done"],
      startDate: day,
      endDate: day,
    },
  ],
  // An unknown id comes back as itself; an empty list is a 400.
  ["POST", "/api/jira/detail/batch", { issueIds: ["0"] }],
  [
    "POST",
    "/api/gerrit/stats",
    {
      ldaps: [NOBODY],
      project: [],
      includeAllProjects: false,
      startDate: day,
      endDate: day,
    },
  ],
  [
    "POST",
    "/api/calendar/events",
    {
      ldaps: [NOBODY],
      calendarIds: ["personal"],
      startDate: day,
      endDate: day,
    },
  ],
];

const pathOf = (url) => new URL(url, "https://x").pathname;

/** Expect 403 from each call, declaring it so the guard accepts it. */
async function expectRefused(page, calls) {
  for (const [method, url] of calls) {
    page.expectApiError({
      method,
      path: new RegExp(`^${pathOf(url).replace(/\//g, "\\/")}$`),
      status: 403,
    });
  }
  for (const [method, url, body] of calls) {
    const res = await callApi(page, method, url, body);
    expect(res.status, `${method} ${url}`).toBe(403);
  }
}

async function expectAnswered(page, calls) {
  for (const [method, url, body] of calls) {
    const res = await callApi(page, method, url, body);
    expect(res.status, `${method} ${url}`).toBe(200);
  }
}

/** The summary gets past the permission check: refused for its dates. */
async function expectSummaryPastGate(page) {
  const [method, url, body] = SUMMARY_CALL;
  page.expectApiError({ method, path: /^\/api\/summary$/, status: 400 });
  const res = await callApi(page, method, url, body);
  expect(res.status).toBe(400);
  expect(res.json.message).toBe(
    `End date ${body.endDate} cannot be earlier than start date ${body.startDate}.`,
  );
}

async function openHome(page) {
  await page.goto("/");
  await expect(link(page, "Personal Dashboard")).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("who reaches the activity pages", { tag: "@dashboard" }, () => {
  for (const role of ["reviewer", "reviewer2", "member", "readonly"]) {
    test(`${role} has neither page and every call behind them is refused`, async ({
      as,
    }) => {
      const page = await as(role);
      expect(page.account.permissions).not.toContain(DASHBOARD);
      expect(page.account.permissions).not.toContain(ACTIVITY);
      await openHome(page);
      // The sidebar is drawn from /api/permissions/me, already answered.
      await expect(link(page, "Open Positions")).toBeVisible();
      await expect(link(page, "Dashboard")).toHaveCount(0);
      await expect(link(page, "DataSearch")).toHaveCount(0);

      const calls = recordCalls(
        page,
        /^\/api\/(summary$|microsoft\/|google\/|jira\/|gerrit\/|calendar\/)/,
      );
      for (const path of ["/dashboard", "/datasearch"]) {
        await page.goto(path);
        await expect(page, `${path} is refused`).toHaveURL(/\/access-denied$/);
      }
      expect(calls, "the refused pages fetched nothing").toEqual([]);

      await expectRefused(page, [SUMMARY_CALL, ...ACTIVITY_CALLS]);
    });
  }

  test("admin reaches both pages from the sidebar and every call answers", async ({
    as,
  }) => {
    const page = await as("admin");
    const loads = await stubSummary(page, { rowsFor: () => [], times: 1 });
    await openHome(page);
    await link(page, "Dashboard").click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect.poll(() => loads.length).toBe(1);
    const topics = apiResponse(page, "GET", "/api/microsoft/chat/topics");
    await link(page, "DataSearch").click();
    await expect(page).toHaveURL(/\/datasearch$/);
    expect((await topics).status()).toBe(200);
    await expectSummaryPastGate(page);
    await expectAnswered(page, ACTIVITY_CALLS);
  });

  test("dashboard.activity_summary.read alone opens the Dashboard and nothing of DataSearch", async ({
    as,
  }) => {
    test.skip(!databaseUrl(), "needs the test database to grant");
    const page = await as("readonly");
    // The Personal Dashboard it lands on asks for its own summary, which is
    // refused for want of a company address (the last test); the guard
    // knows that 403.
    await withGrant(page.account.userId, DASHBOARD, async () => {
      const ldapCalls = recordCalls(page, /^\/api\/microsoft\/[a-z]+\/ldaps$/);
      await openHome(page);
      await expect(link(page, "Dashboard")).toBeVisible();
      await expect(link(page, "DataSearch")).toHaveCount(0);

      // Only the page's own load; the probe below goes to the server. The
      // load's answer is the stub's, so this checks only that the page draws
      // it: the member count comes from the summary itself, so a Dashboard
      // reader needs no access to the LDAP list (PUR-777 #728).
      await stubSummary(page, { times: 1 });
      const summary = apiResponse(page, "POST", "/api/summary");
      await link(page, "Dashboard").click();
      const res = await summary;
      const rows = (await res.json()).data;
      await expect(
        page.getByTestId("card-Members").locator(".text-lg"),
      ).toHaveText(String(rows.length));
      expect(ldapCalls).toEqual([]);
      await expectSummaryPastGate(page);

      await page.goto("/datasearch");
      await expect(page).toHaveURL(/\/access-denied$/);
      await expectRefused(page, ACTIVITY_CALLS);
    });
  });

  test("internal_activity.read alone opens DataSearch with its member picker, and not the Dashboard", async ({
    as,
  }) => {
    test.skip(!databaseUrl(), "needs the test database to grant");
    const page = await as("readonly");
    await withGrant(page.account.userId, ACTIVITY, async () => {
      await openHome(page);
      await expect(link(page, "DataSearch")).toBeVisible();
      await expect(link(page, "Dashboard")).toHaveCount(0);

      const topics = apiResponse(page, "GET", "/api/microsoft/chat/topics");
      await link(page, "DataSearch").click();
      expect((await topics).status()).toBe(200);
      // The picker's LDAP list is gated on internal_activity.read since
      // PUR-777 #729; before, this account got a 403 and an empty picker.
      const list = apiResponse(page, "GET", "/api/microsoft/active/ldaps");
      await page.getByRole("button", { name: "LDAP", exact: true }).click();
      const res = await list;
      expect(res.status()).toBe(200);
      const data = (await res.json()).data;
      const employees = Object.keys(data.employees?.active ?? {}).length;
      expect(employees).toBeGreaterThan(0);
      await expect(
        page.getByRole("dialog").getByRole("checkbox", {
          name: `employees (0/${employees})`,
        }),
      ).toBeVisible();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Cancel" })
        .click();

      await page.goto("/dashboard");
      await expect(page).toHaveURL(/\/access-denied$/);
      await expectRefused(page, [SUMMARY_CALL]);
      await expectAnswered(page, ACTIVITY_CALLS);
    });
  });

  test("a Dashboard reader without a company address is refused a personal summary", async ({
    as,
  }) => {
    // PUR-804: the ldap comes only from a confirmed CircleCat address, and
    // e2e-readonly signs in with a personal one. The refusal comes before
    // any Redis read; the card keeps its zeros.
    test.skip(!databaseUrl(), "needs the test database to grant");
    test.skip(
      flag("view-personal-summary") !== true,
      "view-personal-summary is not declared on",
    );
    const page = await as("readonly");
    await withGrant(page.account.userId, DASHBOARD, async () => {
      const mine = apiResponse(page, "POST", "/api/summary/me");
      await page.goto("/dashboard/me");
      const res = await mine;
      expect(res.status()).toBe(403);
      expect((await res.json()).message).toBe(
        "The activity summary needs a confirmed CircleCat address on the account.",
      );
      await expect(
        page
          .locator('[data-slot="card"]')
          .filter({ hasText: "Work Activity Data" }),
      ).toContainText("Chat Messages Sent0");
    });
  });
});
