import { test, expect } from "../../fixtures.js";
import {
  callApi,
  lastEventId,
  openAccount,
  opsId,
  opsName,
  rowsOf,
  successToast,
  userEventRecipients,
  userState,
} from "./helpers.js";

// Block requests as the account console sees them. e2e-admin raises them
// through the API (the console only blocks directly; raising happens on a
// mentorship or recruiting page, which the mentorship and recruiting specs
// cover), naming e2e-reviewer; only the named reviewer sees and decides
// one, only the raiser moves it. Every notification goes to a test account:
// raised to the reviewer, reassigned to both reviewers, decided to the
// raiser. The person blocked is told nothing.
//
//   Ops Approve    raised, reassigned to e2e-reviewer2, approved
//   Ops Reject     raised, rejected with a reason
//   Ops Supersede  raised, then blocked directly by e2e-admin: superseded
//   Ops Notify     the same through the API, checking who is told (PUR-642)

async function raise(page, userId, reviewerId, reason) {
  const res = await callApi(
    page,
    "POST",
    "/api/block-requests?raised_from=mentorship_participant",
    { userId, reviewerId, reason },
  );
  expect(res.status, JSON.stringify(res.json)).toBe(200);
  return res.json.data.id;
}

const pendingFor = async (page) =>
  (await callApi(page, "GET", "/api/block-requests")).json.data;

const requestStatus = (id) =>
  rowsOf(`SELECT status FROM approval_request WHERE request_id = ${id}`)[0][0];

const card = (page) =>
  page.locator("section").filter({
    has: page.getByRole("heading", {
      name: "Block request awaiting your decision",
    }),
  });

/** The list's banner of requests waiting on the viewer. */
async function expectBanner(page, count) {
  await page.goto("/admin/accounts");
  await expect(
    page.getByRole("heading", { level: 1, name: "Accounts" }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(
      `${count} block request${count === 1 ? "" : "s"} awaiting your decision`,
    ),
  ).toBeVisible({ timeout: 15_000 });
}

test.describe("block requests on the console", { tag: "@accounts" }, () => {
  test("a request reaches only its reviewer, moves when the raiser reassigns it, and blocks once approved", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const second = await as("reviewer2");
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const id = opsId(page, "approve");
    const since = lastEventId();
    await page.goto("/admin/accounts");
    const requestId = await raise(
      page,
      id,
      reviewer.account.userId,
      "e2e regression",
    );

    // The reviewer's banner counts what waits on them, this request included.
    await reviewer.goto("/admin/accounts");
    const mine = await pendingFor(reviewer);
    expect(mine.map((r) => r.id)).toContain(requestId);
    await expectBanner(reviewer, mine.length);
    await reviewer.getByRole("button", { name: "Show them" }).click();
    await expect(reviewer.getByTestId(`account-row-${id}`)).toContainText(
      "Block requested",
    );
    await expect(
      reviewer.getByText("Showing the accounts your block requests are about."),
    ).toBeVisible();
    await reviewer.getByRole("button", { name: "Show all accounts" }).click();
    await openAccount(reviewer, id, opsName("approve"));
    await expect(card(reviewer)).toContainText("from mentorship participant");
    await expect(card(reviewer)).toContainText("e2e regression");

    // Nobody else sees it: not e2e-reviewer2, not the raiser.
    await second.goto("/admin/accounts");
    expect((await pendingFor(second)).map((r) => r.id)).not.toContain(
      requestId,
    );
    await openAccount(second, id, opsName("approve"));
    await expect(card(second)).toHaveCount(0);
    await expect(
      second.getByText("Block requested", { exact: true }),
    ).toHaveCount(0);
    await openAccount(page, id, opsName("approve"));
    await expect(card(page)).toHaveCount(0);

    // Only the raiser may move it.
    reviewer.expectApiError({
      method: "POST",
      path: new RegExp(`^/api/block-requests/${requestId}/reassign$`),
      status: 403,
    });
    const refused = await callApi(
      reviewer,
      "POST",
      `/api/block-requests/${requestId}/reassign`,
      { reviewerId: second.account.userId },
    );
    expect(refused.status).toBe(403);
    const moved = await callApi(
      page,
      "POST",
      `/api/block-requests/${requestId}/reassign`,
      { reviewerId: second.account.userId },
    );
    expect(moved.status, JSON.stringify(moved.json)).toBe(200);
    expect((await pendingFor(reviewer)).map((r) => r.id)).not.toContain(
      requestId,
    );
    expect((await pendingFor(second)).map((r) => r.id)).toContain(requestId);

    await openAccount(second, id, opsName("approve"));
    await card(second)
      .getByRole("button", { name: "Approve and block" })
      .click();
    const confirm = second.getByRole("dialog");
    await expect(
      confirm.getByRole("heading", { name: `Block ${opsName("approve")}?` }),
    ).toBeVisible();
    await confirm.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(successToast(second, "Request approved.")).toBeVisible();
    const header = second
      .getByRole("heading", { level: 1, name: opsName("approve") })
      .locator("..");
    await expect(header.getByText("Blocked", { exact: true })).toBeVisible();
    await expect(card(second)).toHaveCount(0);
    expect(userState(id)).toEqual({ active: true, blocked: true });
    expect(requestStatus(requestId)).toBe("approved");

    const raiser = page.account.userId;
    const first = reviewer.account.userId;
    const next = second.account.userId;
    expect(userEventRecipients(id, since)).toEqual([
      { type: "user.block_requested", to: [first] },
      {
        type: "user.block_request_reassigned",
        to: [first, next].sort((a, b) => a - b),
      },
      { type: "user.blocked", to: [] },
      { type: "user.block_request_decided", to: [raiser] },
    ]);
  });

  test("a rejected request leaves the person unblocked and tells the raiser why", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const id = opsId(page, "reject");
    const since = lastEventId();
    await page.goto("/admin/accounts");
    const requestId = await raise(page, id, reviewer.account.userId, null);

    await openAccount(reviewer, id, opsName("reject"));
    await expect(card(reviewer)).toContainText("No reason given.");
    await card(reviewer).getByRole("button", { name: "Reject" }).click();
    const dialog = reviewer.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Reject this block request" }),
    ).toBeVisible();
    const confirm = dialog.getByRole("button", { name: "Reject", exact: true });
    await expect(confirm, "a reason is required to reject").toBeDisabled();
    await dialog.getByLabel("Reason").fill("e2e regression: not warranted");
    await confirm.click();
    await expect(successToast(reviewer, "Request rejected.")).toBeVisible();
    await expect(card(reviewer)).toHaveCount(0);
    expect(userState(id)).toEqual({ active: true, blocked: false });
    expect(requestStatus(requestId)).toBe("rejected");
    expect(userEventRecipients(id, since)).toEqual([
      { type: "user.block_requested", to: [reviewer.account.userId] },
      { type: "user.block_request_decided", to: [page.account.userId] },
    ]);
    // The bell line carries no reason. It is kept as the request's decision
    // comment (served as decisionNote) and on the decided event.
    expect(
      rowsOf(`
        SELECT r.decision_comment, e.details ->> 'comment'
        FROM approval_request r
        JOIN event e
          ON e.event_type = 'user.block_request_decided'
         AND e.details ->> 'requestId' = r.request_id::text
        WHERE r.request_id = ${requestId}`),
    ).toEqual([
      ["e2e regression: not warranted", "e2e regression: not warranted"],
    ]);
  });

  test("blocking directly closes a pending request as superseded", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const id = opsId(page, "supersede");
    await page.goto("/admin/accounts");
    const requestId = await raise(
      page,
      id,
      reviewer.account.userId,
      "e2e regression",
    );

    await openAccount(page, id, opsName("supersede"));
    await page.getByRole("button", { name: "Block", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/^Reason/).fill("e2e regression: blocked directly");
    await dialog.getByRole("button", { name: "Block", exact: true }).click();
    await expect(successToast(page, "Account blocked.")).toBeVisible();
    expect(userState(id)).toEqual({ active: true, blocked: true });
    expect(requestStatus(requestId)).toBe("superseded");

    await reviewer.goto("/admin/accounts");
    expect((await pendingFor(reviewer)).map((r) => r.id)).not.toContain(
      requestId,
    );
    await openAccount(reviewer, id, opsName("supersede"));
    await expect(card(reviewer)).toHaveCount(0);
    const header = reviewer
      .getByRole("heading", { level: 1, name: opsName("supersede") })
      .locator("..");
    await expect(header.getByText("Blocked", { exact: true })).toBeVisible();
    await expect(
      header.getByText("Block requested", { exact: true }),
    ).toHaveCount(0);

    await reviewer.getByRole("button", { name: "Notifications" }).click();
    await expect(
      reviewer
        .getByRole("dialog")
        .getByText(
          `blocked ${opsName("supersede")} directly, closing the block request about them`,
        ),
    ).toBeVisible();
  });

  test("a request closed as superseded tells the reviewer it was waiting on", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    const page = await as("admin");
    const id = opsId(page, "notify");
    const since = lastEventId();
    await page.goto("/admin/accounts");
    const requestId = await raise(
      page,
      id,
      reviewer.account.userId,
      "e2e regression",
    );
    const blocked = await callApi(
      page,
      "POST",
      `/api/admin/accounts/${id}/block`,
      {
        reason: "e2e regression: blocked directly",
      },
    );
    expect(blocked.status, JSON.stringify(blocked.json)).toBe(200);
    expect(requestStatus(requestId)).toBe("superseded");

    // The raiser blocked directly, so only the reviewer is left waiting.
    expect(userEventRecipients(id, since)).toEqual([
      { type: "user.block_requested", to: [reviewer.account.userId] },
      { type: "user.blocked", to: [] },
      { type: "user.block_request_decided", to: [reviewer.account.userId] },
    ]);
    expect(
      rowsOf(`
        SELECT details ->> 'decision' FROM event
        WHERE event_type = 'user.block_request_decided'
          AND details ->> 'requestId' = '${requestId}'`),
    ).toEqual([["superseded"]]);
  });
});
