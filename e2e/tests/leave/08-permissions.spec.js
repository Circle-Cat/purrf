import { test, expect, settle } from "../../fixtures.js";
import {
  callApi,
  needLeaveSeed,
  personId,
  requestId,
  storedRequest,
} from "./helpers.js";

// Who may do what in leave. Only Leave administration carries a permission
// (leave.admin); deciding and withdrawing are checked against the request's
// own approver and owner. Every request used here is the suite's, so the
// guard lets the calls out and the server's refusal is what is tested.

const sidebarLink = (page) =>
  page.getByRole("link", { name: "Leave Administration", exact: true });

const refused = (method, path, status) => ({ method, path, status });

/** A fetch the guard aborts rejects inside the page; report that as null. */
const tryApi = (page, ...args) => callApi(page, ...args).catch(() => null);

test.describe("leave permissions", { tag: "@leave" }, () => {
  for (const role of ["admin", "reviewer", "reviewer2", "member", "readonly"]) {
    test(`${role} ${role === "admin" ? "sees" : "does not see"} Leave Administration`, async ({
      as,
    }) => {
      const page = await as(role);
      needLeaveSeed(page);
      await page.goto("/");
      await expect(
        page.getByRole("link", { name: "Personal Dashboard", exact: true }),
      ).toBeVisible({ timeout: 20_000 });
      await settle(page);
      if (role === "admin") {
        await expect(sidebarLink(page)).toBeVisible();
        return;
      }
      await expect(sidebarLink(page)).toHaveCount(0);
      await page.goto("/leave/admin");
      await settle(page);
      await expect(page).not.toHaveURL(/\/leave\/admin$/);
      await expect(page.getByRole("tab", { name: "Balances" })).toHaveCount(0);
    });
  }

  test("a member cannot read balances or the ledger, enter holidays or correct a balance", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    page.expectApiError(refused("GET", /^\/api\/leave\/balances$/, 403));
    page.expectApiError(refused("GET", /^\/api\/leave\/ledger$/, 403));
    page.expectApiError(refused("PUT", /^\/api\/leave\/holidays\/2019$/, 403));
    page.expectApiError(refused("POST", /^\/api\/leave\/adjustments$/, 403));
    await page.goto("/");
    const target = personId(page, "Leave Adjust");
    expect((await callApi(page, "GET", "/api/leave/balances")).status).toBe(
      403,
    );
    // Everybody's ledger (PUR-612), also leave.admin only; the member's own
    // is /api/leave/me/ledger.
    expect(
      (await callApi(page, "GET", `/api/leave/ledger?userId=${target}`)).status,
    ).toBe(403);
    expect(
      (
        await callApi(page, "PUT", "/api/leave/holidays/2019", {
          segments: [
            {
              name: "E2E Member 2019",
              startDate: "2019-03-05",
              endDate: "2019-03-05",
              isExchangeable: false,
            },
          ],
        })
      ).status,
    ).toBe(403);
    expect(
      (
        await callApi(page, "POST", "/api/leave/adjustments", {
          userId: target,
          hours: "8",
          effectiveDate: "2019-12-31",
          note: "E2E member",
        })
      ).status,
    ).toBe(403);
  });

  test("only the approver decides and only the owner withdraws", async ({
    as,
  }) => {
    const reviewer2 = await as("reviewer2");
    needLeaveSeed(reviewer2);
    const reviewer = await as("reviewer");
    const member = await as("member");
    for (const page of [reviewer2, reviewer, member]) {
      page.expectApiError(
        refused(
          "POST",
          /^\/api\/leave\/requests\/\d+\/(decision|withdraw)$/,
          403,
        ),
      );
      await page.goto("/");
    }
    const r9 = requestId(reviewer, "R9");
    const m5 = requestId(reviewer, "M5");

    let res = await callApi(
      reviewer2,
      "POST",
      `/api/leave/requests/${r9}/decision`,
      {
        approve: true,
      },
    );
    expect(res.status).toBe(403);
    expect(res.json.message).toBe(
      `Request ${r9} is for somebody else to decide.`,
    );
    res = await callApi(reviewer, "POST", `/api/leave/requests/${m5}/withdraw`);
    expect(res.status).toBe(403);
    expect(res.json.message).toBe(`Request ${m5} belongs to somebody else.`);
    res = await callApi(member, "POST", `/api/leave/requests/${m5}/decision`, {
      approve: true,
    });
    expect(res.status).toBe(403);

    for (const id of [r9, m5]) {
      expect(storedRequest(id)).toMatchObject({
        status: "pending",
        approval: "pending",
      });
    }
  });

  test("a request already closed cannot be decided or withdrawn again", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    needLeaveSeed(reviewer);
    const member = await as("member");
    for (const page of [reviewer, member]) {
      page.expectApiError(
        refused(
          "POST",
          /^\/api\/leave\/requests\/\d+\/(decision|withdraw)$/,
          409,
        ),
      );
      await page.goto("/");
    }
    const h2 = requestId(reviewer, "H2");
    const m3 = requestId(reviewer, "M3");
    let res = await callApi(
      reviewer,
      "POST",
      `/api/leave/requests/${h2}/decision`,
      {
        approve: true,
      },
    );
    expect(res.status).toBe(409);
    expect(res.json.message).toBe(`Request ${h2} is already rejected.`);
    res = await callApi(member, "POST", `/api/leave/requests/${m3}/withdraw`);
    expect(res.status).toBe(409);
    expect(res.json.message).toBe(`Request ${m3} is already rejected.`);
    expect(storedRequest(h2).status).toBe("rejected");
    expect(storedRequest(m3).status).toBe("rejected");
  });

  test("the guard never lets the accrual or annual-close job run", async ({
    as,
  }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    page.expectBlocked(
      /POST \/api\/leave\/jobs\/weekly-accrual: leave jobs are never run/,
    );
    page.expectBlocked(
      /POST \/api\/leave\/jobs\/annual-close: leave jobs are never run/,
    );
    await page.goto("/");
    expect(
      await tryApi(page, "POST", "/api/leave/jobs/weekly-accrual"),
    ).toBeNull();
    expect(
      await tryApi(page, "POST", "/api/leave/jobs/annual-close"),
    ).toBeNull();
  });
});
