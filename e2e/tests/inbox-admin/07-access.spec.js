import { test, expect, settle } from "../../fixtures.js";
import {
  ALIAS,
  callApi,
  inboxThreadReset,
  insertThread,
  openAccount,
  openInbox,
  opsEmail,
  opsId,
  opsName,
  searchInbox,
  stamp,
  threadRowButton,
  userState,
} from "./helpers.js";

// Who cannot reach the Inbox, the account console or the permission page.
// Every write sent here targets a seeded person or an inserted thread, so
// the guard lets it out and the backend must refuse it; nothing changes.
//   e2e-readonly   mentorship.admin.read only
//   e2e-member     nothing
//   e2e-reviewer   user.admin but no Inbox grant and no permission.manage
//   e2e-reviewer2  user.admin and mentorship.admin.write: the Mentorship
//                  Inbox only

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Expect a call to be refused with one of `statuses`. */
async function refused(page, method, path, body, statuses = [403]) {
  const re = new RegExp(`^${escape(path.split("?")[0])}$`);
  for (const status of statuses)
    page.expectApiError({ method, path: re, status });
  const res = await callApi(page, method, path, body);
  expect(statuses, `${method} ${path} -> ${res.status}`).toContain(res.status);
}

function fakeThreads(page) {
  const person = opsId(page, "inbox");
  const tag = `E2E fake ${stamp()} access`;
  const ids = {};
  for (const service of ["mentorship", "recruiting"]) {
    ids[service] = insertThread({
      service,
      subject: `${tag} ${service}`,
      messages: [
        {
          from: opsEmail(person),
          to: ALIAS[service],
          text: "Q",
          minutesAgo: 5,
        },
      ],
    });
  }
  return { tag, ids };
}

test.describe("inbox and console access", { tag: "@accounts" }, () => {
  test.afterEach(() => inboxThreadReset());

  for (const role of ["readonly", "member"]) {
    test(`${role} is turned away from the Inbox, the console and the permission page`, async ({
      as,
    }) => {
      const page = await as(role);
      const { ids } = fakeThreads(page);
      const target = opsId(page, "deactivate");
      for (const path of ["/inbox", "/admin/accounts", "/admin/users"]) {
        await page.goto(path);
        await expect(page, path).toHaveURL(/\/access-denied$/);
      }
      await settle(page);
      await refused(page, "GET", "/api/inbox/threads");
      await refused(page, "GET", "/api/inbox/count");
      await refused(
        page,
        "POST",
        `/api/inbox/threads/${ids.mentorship}/archive`,
      );
      await refused(
        page,
        "PUT",
        `/api/inbox/threads/${ids.mentorship}/assignment`,
        {
          userId: page.seed.byName["Mentee R1"],
          roundId: page.seed.roundId,
        },
      );
      await refused(page, "GET", "/api/admin/accounts");
      await refused(
        page,
        "POST",
        `/api/admin/accounts/${target}/deactivate`,
        {},
      );
      await refused(page, "POST", `/api/admin/accounts/${target}/block`, {
        reason: "e2e regression: should be refused",
      });
      await refused(page, "GET", "/api/block-requests");
      await refused(
        page,
        "POST",
        `/api/admin/users/${opsId(page, "grant")}/permissions/grant`,
        {
          permissionNames: ["internal_activity.read"],
        },
      );
      expect(userState(target)).toEqual({ active: true, blocked: false });
    });
  }

  test("an account admin without permission.manage or an Inbox grant sees the console only", async ({
    as,
  }) => {
    const page = await as("reviewer");
    const { ids } = fakeThreads(page);
    const grant = opsId(page, "grant");
    await page.goto("/inbox");
    await expect(page).toHaveURL(/\/access-denied$/);
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/access-denied$/);
    await openAccount(page, grant, opsName("grant"));
    await expect(
      page.getByRole("link", { name: "Manage permissions →" }),
    ).toHaveCount(0);
    await refused(page, "GET", "/api/inbox/threads");
    await refused(page, "POST", `/api/inbox/threads/${ids.recruiting}/archive`);
    await refused(page, "GET", "/api/admin/users");
    await refused(page, "POST", `/api/admin/users/${grant}/permissions/grant`, {
      permissionNames: ["internal_activity.read"],
    });
    // Raising needs the permission of the page it comes from.
    await refused(
      page,
      "POST",
      "/api/block-requests?raised_from=mentorship_participant",
      {
        userId: opsId(page, "reject"),
        reviewerId: page.seed.testAccounts.find(
          (id) => id !== page.account.userId,
        ),
      },
    );
  });

  test("a mentorship admin sees only Mentorship threads; other services' threads answer as missing", async ({
    as,
  }) => {
    const page = await as("reviewer2");
    const { tag, ids } = fakeThreads(page);
    await openInbox(page);
    const services = page.getByRole("group", { name: "Services" });
    await expect(services.getByRole("button")).toHaveCount(2);
    await expect(services.getByRole("button", { name: /^All/ })).toBeVisible();
    await expect(
      services.getByRole("button", { name: /^Mentorship/ }),
    ).toBeVisible();
    await searchInbox(page, tag);
    await expect(threadRowButton(page, `${tag} mentorship`)).toBeVisible();
    await expect(threadRowButton(page, `${tag} recruiting`)).toHaveCount(0);
    await refused(
      page,
      "GET",
      `/api/inbox/threads/${ids.recruiting}`,
      undefined,
      [400, 404],
    );
    await refused(
      page,
      "POST",
      `/api/inbox/threads/${ids.recruiting}/archive`,
      undefined,
      [400, 404],
    );
    const asked = await callApi(
      page,
      "GET",
      "/api/inbox/threads?service=recruiting",
    );
    // A service the viewer cannot see is not refused: it filters the visible
    // threads down to none, and the service list still names only theirs.
    expect(asked.status, JSON.stringify(asked.json)).toBe(200);
    expect(Array.isArray(asked.json.data.threads)).toBe(true);
    expect(
      asked.json.data.threads,
      "asking for Recruiting shows nothing",
    ).toEqual([]);
    expect(asked.json.data.services.map((s) => s.key)).toEqual(["mentorship"]);
  });
});
