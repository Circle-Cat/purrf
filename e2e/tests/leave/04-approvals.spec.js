import { test, expect } from "../../fixtures.js";
import {
  eventsOf,
  ledgerOfRequest,
  needLeaveSeed,
  openApprovals,
  openMyLeave,
  pendingFor,
  personId,
  requestId,
  rowWith,
  section,
  storedRequest,
} from "./helpers.js";

// Leave Approvals as e2e-reviewer, the approver of every seeded request.
// Each request is found by its unique reason. The 2099 calendar is seeded,
// so approving can recount the hours; R5–R7 are set up to be refused.

const DECIDE = (status) => ({
  method: "POST",
  path: /^\/api\/leave\/requests\/\d+\/decision$/,
  status,
});

/** Approve one waiting row through its confirmation. */
async function approve(page, reason) {
  const row = rowWith(section(page, "Waiting on you"), reason);
  await row.getByRole("button", { name: "Approve" }).click();
  await row.getByRole("button", { name: "Yes, approve" }).click();
}

test.describe("leave approvals", { tag: "@leave" }, () => {
  test("lists what waits on the reviewer with where each balance would land, and what was decided", async ({
    as,
  }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    await openApprovals(page);
    const waiting = section(page, "Waiting on you");
    const decided = section(page, "Decided");
    await expect(waiting.locator("li")).toHaveCount(
      pendingFor(page.account.userId),
    );
    // No company address on a seed person, so no ldap after the name.
    await expect(waiting).not.toContainText("(");

    const r1 = rowWith(waiting, "E2E R1 approve me");
    await expect(r1).toContainText("E2E Leave Approve");
    await expect(r1).toContainText("Mar 3 – Mar 4, 2099 · 16.00 h");
    await expect(r1).toContainText("Balance after24.00h");
    await expect(r1).toContainText("from 40.00h");
    await expect(r1).not.toContainText("unchanged");

    const r2 = rowWith(waiting, "E2E R2 reject me");
    await expect(r2.getByText("Sick leave", { exact: true })).toBeVisible();
    await expect(r2).toContainText("0.00h");
    await expect(r2).toContainText("from 0.00h · unchanged");

    const r3 = rowWith(waiting, "E2E R3 overdraft");
    await expect(r3.getByText("-40.00h", { exact: true })).toHaveClass(
      /text-rose-600/,
    );
    await expect(r3).toContainText(
      "Over the balance, counting their other waiting requests",
    );
    await expect(
      waiting.getByText(
        "Over the balance, counting their other waiting requests",
      ),
    ).toHaveCount(1);

    const r4 = rowWith(waiting, "E2E R4 exchange");
    await expect(r4).toContainText("+ Holiday exchange");
    await expect(r4).toContainText("Balance after8.00h");
    await expect(r4).toContainText("from 0.00h");

    const r9 = rowWith(waiting, "E2E R9 late");
    await expect(r9).toContainText(
      "Submitted with less than 2 working days' notice",
    );
    await expect(
      waiting.getByText("Submitted with less than 2 working days' notice"),
    ).toHaveCount(2); // R9 and the member's M5

    const h1 = rowWith(decided, "E2E H1 approved");
    await expect(h1).toContainText("Approved");
    await expect(h1).toContainText("Approved over the balance");
    await expect(h1.getByRole("button")).toHaveCount(0);
    const h2 = rowWith(decided, "E2E H2 rejected");
    await expect(h2).toContainText("Rejected");
    await expect(h2).toContainText("Reason: E2E H2 clashes with the release");
    await expect(rowWith(decided, "E2E H3 withdrawn")).toContainText(
      "Withdrawn",
    );
    await expect(rowWith(decided, "E2E M3 rejected")).toContainText(
      "Reason: E2E M3 please move it",
    );
    await expect(decided.getByRole("button")).toHaveCount(0);
  });

  test("approving asks once more, then writes the deduction and tells the employee", async ({
    as,
  }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    const id = requestId(page, "R1");
    const me = page.account.userId;
    const owner = personId(page, "Leave Approve");
    await openApprovals(page);
    const row = rowWith(section(page, "Waiting on you"), "E2E R1 approve me");

    const writes = [];
    page.on("request", (r) => {
      if (r.method() === "POST") writes.push(new URL(r.url()).pathname);
    });
    await row.getByRole("button", { name: "Approve" }).click();
    await expect(row).toContainText("Approve for good?");
    await row.getByRole("button", { name: "Cancel" }).click();
    await expect(row.getByRole("button", { name: "Approve" })).toBeVisible();
    expect(writes).toEqual([]);

    await approve(page, "E2E R1 approve me");
    const done = rowWith(section(page, "Decided"), "E2E R1 approve me");
    await expect(done).toContainText("Approved");
    await expect(done).not.toContainText("Approved over the balance");
    await expect(
      rowWith(section(page, "Waiting on you"), "E2E R1 approve me"),
    ).toHaveCount(0);

    expect(storedRequest(id)).toMatchObject({
      status: "approved",
      approval: "approved",
      decidedBy: me,
      isOverdraft: false,
    });
    expect(ledgerOfRequest(id)).toEqual([
      ["leave_deduction", "-16.00", "2099-03-03", String(me)],
    ]);
    expect(eventsOf(id)).toEqual([
      {
        type: "leave.request_decided",
        decision: "approved",
        actor: me,
        recipients: [owner],
      },
    ]);
  });

  test("rejecting needs a reason, writes nothing to the ledger and tells the employee", async ({
    as,
  }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    const id = requestId(page, "R2");
    const me = page.account.userId;
    await openApprovals(page);
    const row = rowWith(section(page, "Waiting on you"), "E2E R2 reject me");
    await row.getByRole("button", { name: "Reject" }).click();
    const reject = row.getByRole("button", { name: "Reject" });
    await expect(reject).toBeDisabled();
    await row.getByLabel("Reason (required, the employee is told)").fill("   ");
    await expect(reject).toBeDisabled();
    await row
      .getByLabel("Reason (required, the employee is told)")
      .fill("E2E not this week");
    await reject.click();

    const done = rowWith(section(page, "Decided"), "E2E R2 reject me");
    await expect(done).toContainText("Rejected");
    await expect(done).toContainText("Reason: E2E not this week");
    expect(storedRequest(id)).toMatchObject({
      status: "rejected",
      approval: "rejected",
      decidedBy: me,
      comment: "E2E not this week",
    });
    expect(ledgerOfRequest(id)).toEqual([]);
    expect(eventsOf(id)).toEqual([
      {
        type: "leave.request_decided",
        decision: "rejected",
        actor: me,
        recipients: [personId(page, "Leave Reject")],
      },
    ]);
  });

  test("approving over the balance is allowed and keeps the overdraft mark", async ({
    as,
  }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    const id = requestId(page, "R3");
    await openApprovals(page);
    await approve(page, "E2E R3 overdraft");
    const done = rowWith(section(page, "Decided"), "E2E R3 overdraft");
    await expect(done).toContainText("Approved over the balance");
    expect(storedRequest(id)).toMatchObject({
      status: "approved",
      isOverdraft: true,
    });
    expect(ledgerOfRequest(id)).toEqual([
      ["leave_deduction", "-40.00", "2099-03-17", String(page.account.userId)],
    ]);
  });

  test("approving a holiday exchange credits the hours", async ({ as }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    const id = requestId(page, "R4");
    await openApprovals(page);
    await approve(page, "E2E R4 exchange");
    await expect(
      rowWith(section(page, "Decided"), "E2E R4 exchange"),
    ).toContainText("Approved");
    expect(storedRequest(id).status).toBe("approved");
    expect(ledgerOfRequest(id)).toEqual([
      ["exchange_credit", "8.00", "2099-06-02", String(page.account.userId)],
    ]);
  });

  test("an approval that no longer holds is refused in the server's words and stays waiting", async ({
    as,
  }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    page.expectApiError(DECIDE(409));
    await openApprovals(page);
    const cases = [
      [
        "R5",
        "E2E R5 recount",
        "This request is for 8.00 hours, but with the company holidays entered since it comes to 0.00.",
      ],
      ["R6", "E2E R6 started", "This leave started on 2019-10-08"],
      [
        "R7",
        "E2E R7 inactive",
        "This person's account is no longer active, so their leave cannot be approved.",
      ],
    ];
    for (const [key, reason, message] of cases) {
      const id = requestId(page, key);
      await approve(page, reason);
      await expect(page.locator("p.text-red-700")).toContainText(message);
      await expect(
        rowWith(section(page, "Waiting on you"), reason),
      ).toBeVisible();
      expect(storedRequest(id)).toMatchObject({
        status: "pending",
        approval: "pending",
      });
      expect(ledgerOfRequest(id)).toEqual([]);
      expect(eventsOf(id)).toEqual([]);
    }
  });

  test("the member sees their approved request in the bell, My Leave and Balance history", async ({
    as,
  }) => {
    const reviewer = await as("reviewer");
    needLeaveSeed(reviewer);
    const id = requestId(reviewer, "M2");
    await openApprovals(reviewer);
    await approve(reviewer, "E2E M2 approve me");
    await expect(
      rowWith(section(reviewer, "Decided"), "E2E M2 approve me"),
    ).toContainText("Approved");
    const member = await as("member");
    expect(eventsOf(id)).toEqual([
      {
        type: "leave.request_decided",
        decision: "approved",
        actor: reviewer.account.userId,
        recipients: [member.account.userId],
      },
    ]);

    await openMyLeave(member);
    await expect(rowWith(member, "E2E M2 approve me")).toContainText(
      "Approved",
    );
    await member.getByRole("button", { name: "Notifications" }).click();
    await expect(
      member
        .getByRole("dialog")
        .getByText("approved your paid leave, Jul 14, 2099"),
    ).toBeVisible({ timeout: 15_000 });
    await member.keyboard.press("Escape");

    await member.goto("/leave/balance-history");
    const entry = member
      .locator("li")
      .filter({ hasText: "Jul 14, 2099" })
      .filter({ hasText: "Leave taken" });
    await expect(entry).toContainText("-8.00 h");
  });

  test("somebody nothing was filed against sees empty lists", async ({
    as,
  }) => {
    const page = await as("reviewer2");
    needLeaveSeed(page);
    await openApprovals(page);
    await expect(page.getByText("Nothing is waiting on you.")).toBeVisible();
    await expect(page.getByText("Nothing decided yet.")).toBeVisible();
  });
});
