import { test, expect, expectNoErrorToast } from "../../fixtures.js";
import {
  allLdapsOf,
  apiResponse,
  browserDay,
  callApi,
  consoleErrors,
  groupsQuery,
  recordCalls,
  rememberWeek,
  stubSummary,
  tableHeaders,
  tableRows,
  weekQuery,
} from "./helpers.js";

// The internal activity Dashboard as e2e-admin. Every number on it comes
// from one POST /api/summary (one row per member of the chosen groups); the
// specs hold the cards and the table to that response, and the member count
// to the LDAP list the API gives for the same groups.
//
// A summary reads Redis for every member of the groups (SIDE-EFFECTS.md,
// "Redis budget"), so only the first test sends one to the server, over a
// week. The others answer the page's summaries with that week's rows
// (stubSummary), or let through only a search the server refuses before
// reading anything.

const HEADERS = [
  "LDAP",
  "Jira Tickets (Done)",
  "Merged CLs",
  "Merged LOC",
  "Meeting Hours",
  "Chat Messages Sent",
];

/** The table row the page should draw for one summary row. */
const rowOf = (m) => [
  m.ldap,
  String(m.jira_issue_done),
  String(m.cl_merged),
  String(m.loc_merged),
  String(m.meeting_hours),
  String(m.chat_count),
];

/** The six cards as the page should show them for a summary. */
function cardsOf(rows) {
  const sum = (k) => rows.reduce((n, m) => n + m[k], 0);
  const cents = rows.reduce((n, m) => n + Math.round(m.meeting_hours * 100), 0);
  return {
    Members: String(rows.length),
    "Jira Tickets (Done)": String(sum("jira_issue_done")),
    "Merged CLs": String(sum("cl_merged")),
    "Merged LOC": String(sum("loc_merged")),
    "Meeting Hours": String(cents / 100),
    "Chat Messages Sent": String(sum("chat_count")),
  };
}

const card = (page, title) =>
  page.getByTestId(`card-${title.replace(/\s+/g, "-")}`).locator(".text-lg");

async function shownCards(page) {
  const out = {};
  for (const title of Object.keys(cardsOf([]))) {
    out[title] = (await card(page, title).textContent()).trim();
  }
  return out;
}

// While "Groups are required." shows, the required groups' labels carry a
// "*" that becomes part of the name.
const groupBox = (page, group) =>
  page.getByRole("checkbox", { name: new RegExp(`^${group}\\s*\\*?$`) });
const terminatedBox = (page) =>
  page.getByRole("checkbox", { name: "Include Terminated Members" });
const table = (page) => page.locator("table");

/** Open the Dashboard and return the first summary request and its rows. */
async function openDashboard(page) {
  const first = apiResponse(page, "POST", "/api/summary");
  await page.goto("/dashboard");
  const res = await first;
  // A stubbed answer that could not be made is a 500 naming why.
  expect(res.status(), (await res.json()).message).toBe(200);
  return { body: res.request().postDataJSON(), rows: (await res.json()).data };
}

/** Click Search and return the summary request it sent and its rows. */
async function search(page) {
  const next = apiResponse(page, "POST", "/api/summary");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const res = await next;
  expect(res.status(), (await res.json()).message).toBe(200);
  return { body: res.request().postDataJSON(), rows: (await res.json()).data };
}

/** The page shows exactly what the summary said, row by row and in total. */
async function expectShows(page, rows) {
  await expect
    .poll(() => shownCards(page), { timeout: 15_000 })
    .toEqual(cardsOf(rows));
  expect(await tableRows(table(page))).toEqual(
    rows.length ? rows.map(rowOf) : [["N/A"]],
  );
}

/** The distinct ldaps the API lists for these groups. */
async function directoryCount(page, status, groups) {
  const res = await callApi(
    page,
    "GET",
    `/api/microsoft/${status}/ldaps?${groupsQuery(groups)}`,
  );
  expect(res.status).toBe(200);
  return allLdapsOf(res.json.data).length;
}

test.describe("activity dashboard", { tag: "@dashboard" }, () => {
  test("loads this month for interns and employees, and a week's search shows the summary as returned", async ({
    as,
  }) => {
    const page = await as("admin");
    const errors = consoleErrors(page);
    const ldapCalls = recordCalls(page, /^\/api\/microsoft\/[a-z]+\/ldaps$/);
    // The month so far is answered empty; the week below is the real one.
    await stubSummary(page, { rowsFor: () => [], times: 1 });
    const { body } = await openDashboard(page);
    const today = await browserDay(page);
    expect(body).toEqual({
      startDate: `${today.slice(0, 8)}01`,
      endDate: today,
      includeTerminated: false,
      groups: ["interns", "employees"],
    });

    await expect(page.getByTestId("start-date-input")).toHaveValue(
      body.startDate,
    );
    await expect(page.getByTestId("end-date-input")).toHaveValue(today);
    await expect(groupBox(page, "interns")).toBeChecked();
    await expect(groupBox(page, "employees")).toBeChecked();
    await expect(groupBox(page, "volunteers")).not.toBeChecked();
    await expect(terminatedBox(page)).not.toBeChecked();
    expect(await tableHeaders(table(page))).toEqual(HEADERS);

    const week = weekQuery();
    await page.getByTestId("start-date-input").fill(week.startDate);
    await page.getByTestId("end-date-input").fill(week.endDate);
    const { body: sent, rows } = await search(page);
    expect(sent).toEqual(week);
    rememberWeek(sent, rows);
    // The comparison below only catches a column read from the wrong field
    // where the fields differ; make sure some member has five different
    // numbers.
    expect(
      rows.some(
        (m) =>
          new Set([
            m.jira_issue_done,
            m.cl_merged,
            m.loc_merged,
            m.meeting_hours,
            m.chat_count,
          ]).size === 5,
      ),
      "some member has five different numbers in the week",
    ).toBe(true);
    await expectShows(page, rows);
    // Since PUR-777 the Dashboard needs no LDAP list of its own.
    expect(ldapCalls).toEqual([]);
    // One row per active intern and employee, idle ones included.
    expect(rows.length).toBe(
      await directoryCount(page, "active", ["interns", "employees"]),
    );
    await expectNoErrorToast(page);
    expect(errors).toEqual([]);
  });

  test("groups, terminated members and the date range go into the search, and the page follows the answer", async ({
    as,
  }) => {
    const page = await as("admin");
    // Each search gets its own answer: the week's rows, then a few of them.
    // Both answers are the stub's, so this checks what the page sends and
    // that it draws whatever comes back, not what the server would select.
    await stubSummary(page, {
      rowsFor: async (body, week) =>
        body.groups.length === 1 ? (await week()).slice(0, 3) : week(),
    });
    await openDashboard(page);
    const { startDate: start, endDate: end } = weekQuery();

    await page.getByTestId("start-date-input").fill(start);
    await page.getByTestId("end-date-input").fill(end);
    await groupBox(page, "volunteers").check();
    await terminatedBox(page).check();
    const { body, rows } = await search(page);
    expect(body).toEqual({
      startDate: start,
      endDate: end,
      includeTerminated: true,
      groups: ["interns", "employees", "volunteers"],
    });
    await expectShows(page, rows);

    // Employees alone, active only.
    await groupBox(page, "interns").uncheck();
    await groupBox(page, "volunteers").uncheck();
    await terminatedBox(page).uncheck();
    const narrow = await search(page);
    expect(narrow.body).toEqual({
      startDate: start,
      endDate: end,
      includeTerminated: false,
      groups: ["employees"],
    });
    await expectShows(page, narrow.rows);
  });

  test("a start after the end moves the end along", async ({ as }) => {
    const page = await as("admin");
    await stubSummary(page);
    await openDashboard(page);
    const early = await browserDay(page, -40);
    const later = await browserDay(page, -20);
    await page
      .getByTestId("start-date-input")
      .fill(await browserDay(page, -60));
    await page.getByTestId("end-date-input").fill(early);
    await page.getByTestId("start-date-input").fill(later);
    await expect(page.getByTestId("end-date-input")).toHaveValue(later);
    const { body } = await search(page);
    expect(body).toMatchObject({ startDate: later, endDate: later });
  });

  test("searching without a group asks for one and sends nothing", async ({
    as,
  }) => {
    const page = await as("admin");
    await stubSummary(page);
    const { rows } = await openDashboard(page);
    await expectShows(page, rows);
    const calls = recordCalls(page, /^\/api\/summary$/);
    await groupBox(page, "interns").uncheck();
    await groupBox(page, "employees").uncheck();
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByText("Groups are required.")).toBeVisible();
    // Proving that nothing was sent has no event to wait for: the message
    // shows from the same click that would send the search, so a request
    // sent anyway could leave just after it. Wait a fixed second for one,
    // then check none went.
    await page.waitForTimeout(1_000);
    expect(calls).toEqual([]);
    await expectShows(page, rows);

    await groupBox(page, "employees").check();
    await expect(page.getByText("Groups are required.")).toHaveCount(0);
  });

  test("an answer of zeros shows every member with zeros", async ({ as }) => {
    // The server's side of an idle period is checked per source, for two
    // members, in the DataSearch spec; a summary would read every member.
    // The zeros here are the stub's own, so this case checks the request
    // body and that the page draws an all-zero answer as zeros, not as
    // blanks or N/A.
    const page = await as("admin");
    await stubSummary(page, {
      rowsFor: async (body, week) =>
        body.startDate === "2000-01-01"
          ? (await week()).map((m) => ({
              ...m,
              jira_issue_done: 0,
              cl_merged: 0,
              loc_merged: 0,
              meeting_hours: 0,
              chat_count: 0,
            }))
          : week(),
    });
    await openDashboard(page);
    await page.getByTestId("start-date-input").fill("2000-01-01");
    await page.getByTestId("end-date-input").fill("2000-01-07");
    const { body, rows } = await search(page);
    expect(body).toMatchObject({
      startDate: "2000-01-01",
      endDate: "2000-01-07",
    });
    await expectShows(page, rows);
  });

  test("the columns sort both ways and keep each member's row together", async ({
    as,
  }) => {
    const page = await as("admin");
    await stubSummary(page);
    const { rows } = await openDashboard(page);
    await expectShows(page, rows);
    const expected = rows.map(rowOf);
    const header = (name) =>
      table(page).locator("thead th").filter({ hasText: name });

    for (const [name, col] of [
      ["Meeting Hours", 4],
      ["Merged LOC", 3],
    ]) {
      await header(name).click();
      await expect(header(name)).toHaveAttribute("aria-sort", "ascending");
      let shown = await tableRows(table(page));
      const values = shown.map((r) => Number(r[col]));
      expect(values).toEqual([...values].sort((a, b) => a - b));
      expect([...shown].sort()).toEqual([...expected].sort());

      await header(name).click();
      await expect(header(name)).toHaveAttribute("aria-sort", "descending");
      shown = await tableRows(table(page));
      expect(shown.map((r) => Number(r[col]))).toEqual(
        [...values].sort((a, b) => b - a),
      );
    }

    await header("LDAP").click();
    await expect(header("LDAP")).toHaveAttribute("aria-sort", "ascending");
    const byLdap = await page.evaluate(
      (ldaps) => [...ldaps].sort((a, b) => String(a).localeCompare(String(b))),
      rows.map((m) => m.ldap),
    );
    expect((await tableRows(table(page))).map((r) => r[0])).toEqual(byLdap);
  });

  test("an end date before the start is refused by the API", async ({ as }) => {
    // The end field's min is the start, but a typed date gets past it.
    const page = await as("admin");
    page.expectApiError({
      method: "POST",
      path: /^\/api\/summary$/,
      status: 400,
    });
    // The search itself is refused before Redis is read.
    await stubSummary(page, { times: 1 });
    const { rows } = await openDashboard(page);
    await expectShows(page, rows);
    const start = await browserDay(page, -5);
    const end = await browserDay(page, -10);
    await page.getByTestId("start-date-input").fill(start);
    await page.getByTestId("end-date-input").fill(end);
    const next = apiResponse(page, "POST", "/api/summary");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    const res = await next;
    expect(res.status()).toBe(400);
    expect((await res.json()).message).toBe(
      `End date ${end} cannot be earlier than start date ${start}.`,
    );
  });

  test("a failed search says so instead of leaving the last answer under the new filters", async ({
    as,
  }) => {
    // PUR-802: the reason shows under the filters, the table empties and the
    // cards show a dash, not the previous period's numbers.
    const page = await as("admin");
    page.expectApiError({
      method: "POST",
      path: /^\/api\/summary$/,
      status: 400,
    });
    await stubSummary(page, { times: 1 });
    const { rows } = await openDashboard(page);
    await expectShows(page, rows);
    await page.getByTestId("start-date-input").fill(await browserDay(page, -5));
    await page.getByTestId("end-date-input").fill(await browserDay(page, -10));
    const next = apiResponse(page, "POST", "/api/summary");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    const res = await next;
    expect(res.status()).toBe(400);
    await expect(page.getByRole("alert")).toHaveText(
      (await res.json()).message,
      { timeout: 5_000 },
    );
    expect(await shownCards(page)).toEqual(
      Object.fromEntries(Object.keys(cardsOf([])).map((t) => [t, "—"])),
    );
    expect(await tableRows(table(page))).toEqual([["N/A"]]);
  });

  test("the summary API answers an empty group list with a client error, not a 500", async ({
    as,
  }) => {
    // PUR-803: the request is refused before it reaches the service. The page
    // itself never sends one.
    const page = await as("admin");
    page.expectApiError({
      method: "POST",
      path: /^\/api\/summary$/,
      status: 400,
    });
    await stubSummary(page, { times: 1 });
    await openDashboard(page);
    const res = await callApi(page, "POST", "/api/summary", {
      startDate: await browserDay(page, -5),
      endDate: await browserDay(page),
      groups: [],
      includeTerminated: false,
    });
    expect(res.status).toBe(400);
  });
});
