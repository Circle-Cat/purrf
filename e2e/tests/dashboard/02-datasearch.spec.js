import { test, expect, expectNoErrorToast } from "../../fixtures.js";
import {
  GROUPS,
  apiResponse,
  browserDay,
  callApi,
  consoleErrors,
  groupsQuery,
  ldapsOf,
  recordCalls,
  tableHeaders,
  tableRows,
  weekQuery,
  weekRows,
} from "./helpers.js";

// DataSearch as e2e-admin: pick members from the LDAP list, data sources
// from the five source lists, a period, then read each tab. The members are
// the two busiest of the week the Dashboard spec summarized (weekRows), and
// every cell is checked against the response the tab got. Every query
// reads Redis per member, so it names those two and spans at most seven
// days (SIDE-EFFECTS.md, "Redis budget").

const SOURCE_LISTS = [
  "/api/microsoft/chat/topics",
  "/api/google/chat/spaces",
  "/api/jira/projects",
  "/api/gerrit/projects",
  "/api/calendar/calendars",
];
const QUERIES =
  /^\/api\/(microsoft\/chat\/count|google\/chat\/count|jira\/brief|jira\/detail\/batch|gerrit\/stats|calendar\/events)$/;

const dialog = (page) => page.getByRole("dialog");
const ldapChip = (page) =>
  page.getByRole("button", { name: /^LDAP( \(\d+\))?$/ });
const tabs = (page) => page.getByTestId("tab-component");
const tab = (page, name) => page.getByTestId(`tab-button-${name}`);
const searchButton = (page) =>
  page.getByRole("button", { name: "Search", exact: true });

/** Open DataSearch and return the five source lists it loaded. */
async function openDataSearch(page) {
  const lists = SOURCE_LISTS.map((p) => apiResponse(page, "GET", p));
  await page.goto("/datasearch");
  const out = {};
  for (const [i, res] of (await Promise.all(lists)).entries()) {
    expect(res.status(), SOURCE_LISTS[i]).toBe(200);
    out[SOURCE_LISTS[i]] = (await res.json()).data;
  }
  await expect(page.getByTestId("data-search-page")).toBeVisible();
  return {
    topics: out["/api/microsoft/chat/topics"],
    spaces: out["/api/google/chat/spaces"],
    jira: out["/api/jira/projects"],
    gerrit: out["/api/gerrit/projects"],
    calendars: out["/api/calendar/calendars"],
  };
}

/**
 * The two interns or employees with the most kinds of activity in the
 * week, by its summary, with their directory names.
 */
async function busyMembers(page) {
  const kinds = (m) =>
    ["jira_issue_done", "cl_merged", "meeting_hours", "chat_count"].filter(
      (k) => m[k] > 0,
    ).length;
  const picked = weekRows()
    .filter((m) => !/^\d+$/.test(m.ldap))
    .sort(
      (a, b) =>
        kinds(b) - kinds(a) ||
        b.jira_issue_done + b.cl_merged - (a.jira_issue_done + a.cl_merged),
    )
    .slice(0, 2);
  expect(picked.length, "two members to search for").toBe(2);
  expect(kinds(picked[0]), "someone was busy in every source").toBe(4);
  const dir = await callApi(
    page,
    "GET",
    `/api/microsoft/active/ldaps?${groupsQuery(GROUPS)}`,
  );
  const names = Object.assign(
    {},
    ...GROUPS.map((g) => dir.json.data?.[g]?.active ?? {}),
  );
  return picked.map((m) => ({ ldap: m.ldap, name: names[m.ldap] ?? "" }));
}

/** Member rows of the open picker (group rows carry the big heading). */
const memberRows = (page) =>
  dialog(page)
    .locator('button[role="checkbox"]')
    .filter({ hasNot: page.locator(".text-\\[22px\\]") });

const memberButton = (page, ldap) =>
  dialog(page)
    .locator('button[role="checkbox"]')
    .filter({ has: page.getByText(ldap, { exact: true }) })
    .first();

/** Pick members by ldap in the open member picker. */
async function pickMembers(page, members) {
  const box = dialog(page).getByPlaceholder("Search by LDAP or full name");
  for (const { ldap } of members) {
    await box.fill(ldap);
    await memberButton(page, ldap).click();
    await expect(memberButton(page, ldap)).toHaveAttribute(
      "aria-checked",
      "true",
    );
  }
  await box.fill("");
}

async function chooseMembers(page, members) {
  const list = apiResponse(page, "GET", "/api/microsoft/active/ldaps");
  await ldapChip(page).click();
  expect((await list).status()).toBe(200);
  await pickMembers(page, members);
  await dialog(page).getByRole("button", { name: "OK", exact: true }).click();
  await expect(dialog(page)).toHaveCount(0);
  await expect(ldapChip(page)).toHaveText(`LDAP (${members.length})`);
}

const sourceRow = (page, source) =>
  dialog(page).locator('aside [role="button"]').filter({ hasText: source });
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const sourceItem = (page, name) =>
  dialog(page)
    .locator("main label")
    .filter({ hasText: new RegExp(`^\\s*${escape(name.trim())}\\s*$`) });

async function openSources(page) {
  await page.getByRole("button", { name: "Data Source", exact: true }).click();
  await expect(
    dialog(page).getByRole("checkbox", {
      name: "Select all items across all sources",
    }),
  ).toBeVisible();
}

async function confirmSources(page) {
  await dialog(page).getByRole("button", { name: "OK", exact: true }).click();
  await expect(dialog(page)).toHaveCount(0);
}

async function chooseAllSources(page) {
  await openSources(page);
  await dialog(page)
    .getByRole("checkbox", { name: "Select all items across all sources" })
    .check();
  await confirmSources(page);
}

async function setPeriod(page, start, end) {
  await page.getByTestId("end-date-input").fill(end);
  await page.getByTestId("start-date-input").fill(start);
  await expect(page.getByTestId("end-date-input")).toHaveValue(end);
}

/** The chat table the page should draw from the two count responses. */
function chatRows(ms, google, topicName, spaces) {
  const rows = Object.entries(ms ?? {}).map(([ldap, n]) => [
    ldap,
    topicName,
    String(n),
  ]);
  for (const ldap in google ?? {}) {
    for (const id in google[ldap]) {
      rows.push([ldap, spaces[id] ?? id, String(google[ldap][id])]);
    }
  }
  return rows;
}

/** One Jira user table per ldap: [heading, [status, count, points, ">"]…]. */
function jiraTables(brief, statusList) {
  const label = { todo: "To Do", in_progress: "In Progress", done: "Done" };
  const out = [];
  for (const ldap in brief) {
    if (ldap === "time_range") continue;
    out.push([
      ldap,
      statusList.map((s) => [
        label[s],
        String(brief[ldap][s]?.length ?? 0),
        s === "done"
          ? (brief[ldap].done_story_points_total ?? 0).toFixed(1)
          : "-",
        ">",
      ]),
    ]);
  }
  return out;
}

async function shownJiraTables(page) {
  const tables = page.getByTestId("user-table");
  const out = [];
  for (let i = 0; i < (await tables.count()); i += 1) {
    const t = tables.nth(i);
    out.push([
      (await t.locator("h4").textContent()).trim(),
      await t
        .locator(":scope > table > tbody > tr")
        .evaluateAll((rows) =>
          rows.map((tr) =>
            [...tr.querySelectorAll(":scope > td")].map((td) =>
              td.textContent.trim(),
            ),
          ),
        ),
    ]);
  }
  return out;
}

/** The Gerrit table, formatted in the browser as the page formats it. */
const gerritRows = (page, data) =>
  page.evaluate(
    (d) =>
      Object.entries(d ?? {}).map(([ldap, v]) => [
        ldap,
        Number(v.cl_merged ?? 0).toLocaleString(),
        Number(v.loc_merged ?? 0).toLocaleString(),
        Number(v.cl_reviewed ?? 0).toLocaleString(),
        v.cl_under_review == null
          ? "N/A"
          : Number(v.cl_under_review).toLocaleString(),
        Number(v.cl_abandoned ?? 0).toLocaleString(),
      ]),
    data,
  );

/** The Calendar table, with dates and times in the browser's locale. */
const calendarRows = (page, data) =>
  page.evaluate(
    (d) =>
      Object.entries(d ?? {}).flatMap(([ldap, events]) =>
        (events ?? []).flatMap((e) =>
          (e.attendance ?? []).map((a) => {
            const join = new Date(a.join_time);
            const hm = { hour: "2-digit", minute: "2-digit" };
            return [
              ldap,
              e.calendar_name.trim(),
              e.summary.trim(),
              join.toLocaleDateString(),
              join.toLocaleTimeString([], hm),
              new Date(a.leave_time).toLocaleTimeString([], hm),
            ];
          }),
        ),
      ),
    data,
  );

test.describe("data search", { tag: "@dashboard" }, () => {
  test("the source picker lists what the API holds, and Search waits for members, a period and a source", async ({
    as,
  }) => {
    const page = await as("admin");
    const errors = consoleErrors(page);
    const calls = recordCalls(page, QUERIES);
    const lists = await openDataSearch(page);
    await expect(ldapChip(page)).toHaveText("LDAP");
    await expect(page.getByTestId("start-date-input")).toHaveValue("");

    // PUR-808: Search stays disabled, naming what is still missing, in a
    // tooltip on its wrapper (the disabled button gets no hover).
    const whyNot = async (text) => {
      await expect(searchButton(page)).toBeDisabled();
      await searchButton(page).locator("..").hover();
      await expect(page.getByRole("tooltip")).toHaveText(text);
      await page.mouse.move(0, 0);
    };
    await whyNot("Pick members, a date range and a data source first.");
    await openSources(page);
    const expected = {
      Chat: [...Object.values(lists.topics), ...Object.values(lists.spaces)],
      Jira: Object.values(lists.jira),
      Gerrit: lists.gerrit,
      Calendar: lists.calendars.map((c) => c.name),
    };
    for (const [source, names] of Object.entries(expected)) {
      expect(names.length, `${source} has something to pick`).toBeGreaterThan(
        0,
      );
      await sourceRow(page, source).locator("span").click();
      await expect(sourceRow(page, source)).toHaveAttribute(
        "data-active",
        "true",
      );
      expect(
        await dialog(page)
          .locator("main label")
          .evaluateAll((ls) => ls.map((l) => l.textContent.trim())),
      ).toEqual(names.map((n) => n.trim()));
    }
    await sourceRow(page, "Jira").locator("span").click();
    await sourceItem(page, Object.values(lists.jira)[0]).click();
    await confirmSources(page);

    // A source but no members and no period.
    await whyNot("Pick members and a date range first.");
    await setPeriod(
      page,
      await browserDay(page, -7),
      await browserDay(page, -1),
    );
    // A period too, still no members.
    await whyNot("Pick members first.");
    await expect(tabs(page)).toHaveCount(0);
    expect(calls).toEqual([]);
    await expectNoErrorToast(page);
    expect(errors).toEqual([]);
  });

  test("the member picker shows the directory by group, filters, and adds terminated members on request", async ({
    as,
  }) => {
    const page = await as("admin");
    await openDataSearch(page);
    const dir = await callApi(
      page,
      "GET",
      `/api/microsoft/all/ldaps?${groupsQuery(GROUPS)}`,
    );
    expect(dir.status).toBe(200);
    const first = apiResponse(page, "GET", "/api/microsoft/active/ldaps");
    await ldapChip(page).click();
    const res = await first;
    expect(new URL(res.url()).searchParams.getAll("groups[]")).toEqual(GROUPS);
    const activeData = (await res.json()).data;
    await expect(
      dialog(page).getByRole("heading", { name: "Select Members" }),
    ).toBeVisible();

    const groupRow = (g) =>
      dialog(page).getByRole("checkbox", {
        name: new RegExp(`^${g} \\(\\d+/\\d+\\)$`),
      });
    for (const g of GROUPS) {
      const n = ldapsOf(activeData, g, "active").length;
      await expect(groupRow(g)).toHaveAttribute("aria-label", `${g} (0/${n})`);
    }
    const allMembers = memberRows(page);
    const activeCount = GROUPS.reduce(
      (n, g) => n + ldapsOf(activeData, g, "active").length,
      0,
    );
    await expect(allMembers).toHaveCount(activeCount);

    // Search narrows to people whose ldap or name contains the text.
    const [someone] = ldapsOf(activeData, "employees", "active");
    const box = dialog(page).getByPlaceholder("Search by LDAP or full name");
    await box.fill(someone);
    const shown = await memberRows(page).allTextContents();
    expect(shown.length).toBeGreaterThan(0);
    for (const text of shown) {
      expect(text.toLowerCase()).toContain(someone.toLowerCase());
    }
    await box.fill("");

    // Selecting a whole group, then one member less.
    await groupRow("employees").click();
    const employees = ldapsOf(activeData, "employees", "active");
    await expect(groupRow("employees")).toHaveAttribute(
      "aria-label",
      `employees (${employees.length}/${employees.length})`,
    );
    await expect(groupRow("employees")).toHaveAttribute("aria-checked", "true");
    await memberButton(page, employees[0]).click();
    await expect(groupRow("employees")).toHaveAttribute(
      "aria-checked",
      "mixed",
    );
    await expect(
      dialog(page).getByText(`${employees.length - 1} selected`),
    ).toBeVisible();

    // Terminated members come from the "all" list.
    const all = apiResponse(page, "GET", "/api/microsoft/all/ldaps");
    await dialog(page)
      .getByRole("checkbox", { name: "Include Terminated Members" })
      .check();
    const allRes = await all;
    expect(new URL(allRes.url()).searchParams.getAll("groups[]")).toEqual(
      GROUPS,
    );
    const allData = (await allRes.json()).data;
    for (const g of GROUPS) {
      const n =
        ldapsOf(allData, g, "active").length +
        ldapsOf(allData, g, "terminated").length;
      await expect(groupRow(g)).toHaveAttribute(
        "aria-label",
        new RegExp(`^${g} \\(\\d+/${n}\\)$`),
      );
    }
    const terminated = GROUPS.reduce(
      (n, g) => n + ldapsOf(allData, g, "terminated").length,
      0,
    );
    await expect(
      dialog(page).locator(
        'button[role="checkbox"][aria-label$="(terminated)"]',
      ),
    ).toHaveCount(terminated);

    await dialog(page).getByRole("button", { name: "OK", exact: true }).click();
    await expect(ldapChip(page)).toHaveText(`LDAP (${employees.length - 1})`);
  });

  test("searching every source shows each tab as the API answered it", async ({
    as,
  }) => {
    const page = await as("admin");
    const errors = consoleErrors(page);
    const lists = await openDataSearch(page);
    const { startDate: start, endDate: end } = weekQuery();
    const members = await busyMembers(page);
    const ldaps = members.map((m) => m.ldap);

    await chooseMembers(page, members);
    await chooseAllSources(page);
    await setPeriod(page, start, end);

    const msWait = apiResponse(page, "POST", "/api/microsoft/chat/count");
    const googleWait = apiResponse(page, "POST", "/api/google/chat/count");
    await searchButton(page).click();
    await expect(tabs(page)).toBeVisible();
    for (const name of ["Chat", "Jira", "Gerrit", "Calendar"]) {
      await expect(tab(page, name)).toBeEnabled();
    }
    await expect(tab(page, "Chat")).toHaveAttribute("data-state", "active");

    // Chat: Teams and Google Chat counts, one row per member and space.
    const [ms, google] = await Promise.all([msWait, googleWait]);
    expect(ms.request().postDataJSON()).toEqual({
      ldaps,
      startDate: start,
      endDate: end,
    });
    expect(google.request().postDataJSON()).toEqual({
      ldaps,
      startDate: start,
      endDate: end,
      spaceIds: Object.keys(lists.spaces),
    });
    const msData = (await ms.json()).data.result;
    const googleData = (await google.json()).data.result;
    const chatTable = page.locator(".chat-report-container table");
    await expect(chatTable).toBeVisible();
    expect(await tableHeaders(chatTable)).toEqual([
      "LDAP",
      "CHAT SPACE",
      "COUNTS",
    ]);
    expect(await tableRows(chatTable)).toEqual(
      chatRows(
        msData,
        googleData,
        Object.values(lists.topics)[0],
        lists.spaces,
      ),
    );

    // Jira: done issues only, since the period has ended.
    const briefWait = apiResponse(page, "POST", "/api/jira/brief");
    await tab(page, "Jira").click();
    const brief = await briefWait;
    const briefBody = brief.request().postDataJSON();
    expect({
      ...briefBody,
      projectIds: [...briefBody.projectIds].sort(),
    }).toEqual({
      ldaps,
      startDate: start,
      endDate: end,
      projectIds: Object.keys(lists.jira).sort(),
      statusList: ["done"],
    });
    const briefData = (await brief.json()).data;
    await expect(page.getByTestId("user-table")).toHaveCount(ldaps.length);
    expect(await shownJiraTables(page)).toEqual(
      jiraTables(briefData, ["done"]),
    );

    // Opening a member's Done row lists those issues.
    const withDone = ldaps.find((l) => briefData[l]?.done?.length > 0);
    expect(withDone, "a member finished a Jira issue").toBeTruthy();
    const userTable = page.getByTestId("user-table").filter({
      has: page.getByRole("heading", { name: withDone, exact: true }),
    });
    const detailWait = apiResponse(page, "POST", "/api/jira/detail/batch");
    await userTable
      .locator("tbody tr")
      .filter({ hasText: "Done" })
      .first()
      .click();
    const detail = await detailWait;
    expect(detail.request().postDataJSON()).toEqual({
      issueIds: briefData[withDone].done,
    });
    const issues = (await detail.json()).data;
    const fmt = (d) =>
      d ? `${d.slice(0, 4)}/${d.slice(4, 6)}/${d.slice(6, 8)}` : "-";
    const inner = userTable.locator("table table");
    await expect(inner).toBeVisible();
    expect(await tableHeaders(inner)).toEqual([
      "Key",
      "Title",
      "Story Points",
      "Finished Date",
    ]);
    expect(await tableRows(inner)).toEqual(
      issues.map((t) => [
        t.issue_key,
        t.issue_title.trim(),
        String(t.story_point),
        fmt(t.finish_date),
      ]),
    );

    // Gerrit: every project, so all projects count.
    const gerritWait = apiResponse(page, "POST", "/api/gerrit/stats");
    await tab(page, "Gerrit").click();
    const gerrit = await gerritWait;
    expect(gerrit.request().postDataJSON()).toEqual({
      ldaps,
      startDate: start,
      endDate: end,
      project: lists.gerrit,
      includeAllProjects: true,
    });
    const gerritData = (await gerrit.json()).data;
    const gerritTable = page.getByRole("tabpanel").locator("table");
    await expect(gerritTable).toBeVisible();
    expect(await tableHeaders(gerritTable)).toEqual([
      "LDAP",
      "CL MERGED",
      "LOC MERGED",
      "CL REVIEWED",
      "CL UNDER REVIEW (TODAY)",
      "CL ABANDONED",
    ]);
    expect(await tableRows(gerritTable)).toEqual(
      await gerritRows(page, gerritData),
    );

    // Calendar: one row per attendance.
    const calendarWait = apiResponse(page, "POST", "/api/calendar/events");
    await tab(page, "Calendar").click();
    const calendar = await calendarWait;
    expect(calendar.request().postDataJSON()).toEqual({
      ldaps,
      startDate: start,
      endDate: end,
      calendarIds: lists.calendars.map((c) => c.id),
    });
    const calendarData = (await calendar.json()).data;
    const calendarTable = page.locator(".schedule-container table");
    await expect(calendarTable).toBeVisible();
    expect(await tableHeaders(calendarTable)).toEqual([
      "LDAP",
      "CALENDAR",
      "EVENTS",
      "DATE",
      "START TIME",
      "END TIME",
    ]);
    const expected = await calendarRows(page, calendarData);
    expect(expected.length, "the members attended meetings").toBeGreaterThan(0);
    expect(await tableRows(calendarTable)).toEqual(expected);

    await expectNoErrorToast(page);
    expect(errors).toEqual([]);
  });

  test("a narrower selection queries only what was picked, and an open period asks for every Jira status", async ({
    as,
  }) => {
    const page = await as("admin");
    const lists = await openDataSearch(page);
    // Seven days up to today, so the period is still open.
    const start = await browserDay(page, -6);
    const today = await browserDay(page);
    const members = await busyMembers(page);
    const ldaps = members.map((m) => m.ldap);

    // The Jira project of an issue one of them finished in the week.
    const briefAll = await callApi(page, "POST", "/api/jira/brief", {
      ldaps,
      startDate: weekQuery().startDate,
      endDate: weekQuery().endDate,
      projectIds: Object.keys(lists.jira),
      statusList: ["done"],
    });
    const doneId = ldaps
      .map((l) => briefAll.json.data[l]?.done?.[0])
      .find(Boolean);
    expect(doneId, "a finished issue").toBeTruthy();
    const [issue] = (
      await callApi(page, "POST", "/api/jira/detail/batch", {
        issueIds: [doneId],
      })
    ).json.data;
    const projectId = issue.project_id;
    const projectName = lists.jira[projectId];
    expect(projectName, `project ${projectId} is listed`).toBeTruthy();
    const gerritProject = lists.gerrit.includes("purrf")
      ? "purrf"
      : lists.gerrit[0];

    await chooseMembers(page, members);
    await openSources(page);
    await sourceRow(page, "Jira").locator("span").click();
    await sourceItem(page, projectName).getByRole("checkbox").check();
    await sourceRow(page, "Gerrit").locator("span").click();
    await sourceItem(page, gerritProject).getByRole("checkbox").check();
    await confirmSources(page);
    await setPeriod(page, start, today);

    const briefWait = apiResponse(page, "POST", "/api/jira/brief");
    await searchButton(page).click();
    await expect(tab(page, "Chat")).toBeDisabled();
    await expect(tab(page, "Calendar")).toBeDisabled();
    await expect(tab(page, "Jira")).toHaveAttribute("data-state", "active");
    const brief = await briefWait;
    const statusList = ["done", "in_progress", "todo"];
    expect(brief.request().postDataJSON()).toEqual({
      ldaps,
      startDate: start,
      endDate: today,
      projectIds: [projectId],
      statusList,
    });
    const briefData = (await brief.json()).data;
    expect(await shownJiraTables(page)).toEqual(
      jiraTables(briefData, statusList),
    );

    const gerritWait = apiResponse(page, "POST", "/api/gerrit/stats");
    await tab(page, "Gerrit").click();
    const gerrit = await gerritWait;
    expect(gerrit.request().postDataJSON()).toEqual({
      ldaps,
      startDate: start,
      endDate: today,
      project: [gerritProject],
      includeAllProjects: false,
    });
    const gerritTable = page.getByRole("tabpanel").locator("table");
    await expect(gerritTable).toBeVisible();
    expect(await tableRows(gerritTable)).toEqual(
      await gerritRows(page, (await gerrit.json()).data),
    );
  });

  test("a period with no activity shows zeros and an empty calendar", async ({
    as,
  }) => {
    const page = await as("admin");
    const calls = recordCalls(page, /^\/api\/jira\/detail\/batch$/);
    const lists = await openDataSearch(page);
    const members = await busyMembers(page);
    await chooseMembers(page, members);
    await chooseAllSources(page);
    await setPeriod(page, "2000-01-01", "2000-01-07");

    const msWait = apiResponse(page, "POST", "/api/microsoft/chat/count");
    const googleWait = apiResponse(page, "POST", "/api/google/chat/count");
    await searchButton(page).click();
    const [ms, google] = await Promise.all([msWait, googleWait]);
    const chatTable = page.locator(".chat-report-container table");
    await expect(chatTable).toBeVisible();
    const chat = await tableRows(chatTable);
    expect(chat).toEqual(
      chatRows(
        (await ms.json()).data.result,
        (await google.json()).data.result,
        Object.values(lists.topics)[0],
        lists.spaces,
      ),
    );
    for (const row of chat) expect(row[2]).toBe("0");

    await tab(page, "Jira").click();
    await expect(page.getByTestId("user-table")).toHaveCount(members.length);
    for (const [, statuses] of await shownJiraTables(page)) {
      expect(statuses).toEqual([["Done", "0", "0.0", ">"]]);
    }
    await page
      .getByTestId("user-table")
      .first()
      .locator("tbody tr")
      .first()
      .click();
    await expect(
      page.getByTestId("user-table").first().getByText("N/A", { exact: true }),
    ).toBeVisible();
    expect(calls).toEqual([]);

    await tab(page, "Gerrit").click();
    const gerritTable = page.getByRole("tabpanel").locator("table");
    await expect(gerritTable).toBeVisible();
    for (const row of await tableRows(gerritTable)) {
      expect(row.slice(1)).toEqual(["0", "0", "0", "N/A", "0"]);
    }

    const calendarWait = apiResponse(page, "POST", "/api/calendar/events");
    await tab(page, "Calendar").click();
    const calendar = await calendarWait;
    for (const events of Object.values((await calendar.json()).data)) {
      expect(events).toEqual([]);
    }
    await expect(
      page.getByText("No events found for the given parameters."),
    ).toBeVisible();
  });

  test("changing the period after a search hides the results until Search again", async ({
    as,
  }) => {
    const page = await as("admin");
    await openDataSearch(page);
    const start = await browserDay(page, -7);
    const end = await browserDay(page, -1);
    const members = await busyMembers(page);
    await chooseMembers(page, members);
    await chooseAllSources(page);
    await setPeriod(page, start, end);
    const first = apiResponse(page, "POST", "/api/microsoft/chat/count");
    await searchButton(page).click();
    await first;
    await expect(tabs(page)).toBeVisible();

    const newStart = await browserDay(page, -3);
    await page.getByTestId("start-date-input").fill(newStart);
    await expect(tabs(page)).toHaveCount(0);

    const again = apiResponse(page, "POST", "/api/microsoft/chat/count");
    await searchButton(page).click();
    expect((await again).request().postDataJSON()).toMatchObject({
      startDate: newStart,
      endDate: end,
    });
    await expect(tabs(page)).toBeVisible();
  });

  // By design: Cancel clears the whole selection, including members confirmed
  // before the picker was opened.
  test("Cancel in the member picker clears the members confirmed before", async ({
    as,
  }) => {
    const page = await as("admin");
    await openDataSearch(page);
    const members = await busyMembers(page);
    await chooseMembers(page, members);
    await expect(ldapChip(page)).toHaveText(`LDAP (${members.length})`);
    await ldapChip(page).click();
    await expect(
      dialog(page).getByText(`${members.length} selected`),
    ).toBeVisible();
    await dialog(page).getByRole("button", { name: "Cancel" }).click();
    await expect(dialog(page)).toHaveCount(0);
    await expect(ldapChip(page)).toHaveText("LDAP");
  });
});
