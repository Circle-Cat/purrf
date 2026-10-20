import { test, expect } from "../../fixtures.js";
import {
  eventsOf,
  ledgerOf,
  ledgerOfRequest,
  needLeaveSeed,
  openDashboard,
  openMyLeave,
  requestId,
  rowWith,
  rowsOf,
  standingOf,
  stat,
  storedRequest,
  timeOffCard,
} from "./helpers.js";

// My Leave (/leave/requests) as e2e-member, whose seeded requests are M1–M5,
// all filed against e2e-reviewer.

test.describe("my leave", { tag: "@leave" }, () => {
  test("lists the member's requests, latest first, with what each one is waiting on", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    await openMyLeave(page);
    const rows = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByText("My requests", { exact: true }) })
      .locator("li");
    await expect(rows).toHaveCount(5);
    const reasons = [
      "M5 dentist",
      "M4 flu",
      "M3 rejected",
      "M2 approve me",
      "M1 family trip",
    ];
    for (const [at, reason] of reasons.entries()) {
      await expect(rows.nth(at)).toContainText(`E2E ${reason}`);
    }

    const m5 = rowWith(page, "E2E M5 dentist");
    await expect(m5).toContainText("− Paid leave");
    await expect(m5).toContainText("Waiting for your manager");
    await expect(m5).toContainText("Aug 4, 2099 · 09:00 – 13:00 · 4.00 h");
    await expect(m5).toContainText(
      "Submitted with less than 2 working days' notice",
    );
    await expect(m5.getByRole("button", { name: "Withdraw" })).toBeVisible();

    const m4 = rowWith(page, "E2E M4 flu");
    await expect(m4.getByText("Sick leave", { exact: true })).toBeVisible();
    await expect(m4).toContainText("Approved");
    await expect(m4).toContainText("Jul 28, 2099 · 8.00 h");
    await expect(m4.getByRole("button", { name: "Withdraw" })).toHaveCount(0);

    const m3 = rowWith(page, "E2E M3 rejected");
    await expect(m3).toContainText("Rejected");
    await expect(m3).toContainText(
      "Your manager's reason: E2E M3 please move it",
    );
    await expect(m3.getByRole("button", { name: "Withdraw" })).toHaveCount(0);

    for (const reason of ["E2E M2 approve me", "E2E M1 family trip"]) {
      const row = rowWith(page, reason);
      await expect(row).toContainText("Waiting for your manager");
      await expect(row).not.toContainText("working days' notice");
      await expect(row.getByRole("button", { name: "Withdraw" })).toBeVisible();
    }
  });

  test("withdrawing a waiting request closes it and tells only the approver", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    const id = requestId(page, "M1");
    const me = page.account.userId;
    const ledgerBefore = ledgerOf(me);
    const standingBefore = standingOf(me);
    expect(storedRequest(id).status).toBe("pending");

    await openMyLeave(page);
    const row = rowWith(page, "E2E M1 family trip");
    await row.getByRole("button", { name: "Withdraw" }).click();
    await expect(row).toContainText("Withdrawn");
    await expect(row.getByRole("button", { name: "Withdraw" })).toHaveCount(0);

    const stored = storedRequest(id);
    expect(stored).toMatchObject({
      status: "withdrawn",
      approval: "withdrawn",
      decidedBy: me,
    });
    const approver = Number(
      rowsOf(
        `SELECT approver_user_id FROM leave_request WHERE leave_request_id = ${id}`,
      )[0][0],
    );
    expect(page.seed.testAccounts).toContain(approver);
    expect(eventsOf(id)).toEqual([
      {
        type: "leave.request_decided",
        decision: "withdrawn",
        actor: me,
        recipients: [approver],
      },
    ]);
    expect(ledgerOfRequest(id)).toEqual([]);
    expect(ledgerOf(me)).toEqual(ledgerBefore);

    // M1 is paid leave: its hours leave Pending and come back to Available.
    // Held to the database, not to the seed's 12 h / 36 h, which only hold
    // when no other file has moved the member's requests or ledger.
    const [[m1Hours]] = rowsOf(
      `SELECT hours FROM leave_request WHERE leave_request_id = ${id}`,
    );
    const standing = standingOf(me);
    expect(Number(standing.pending)).toBe(
      Number(standingBefore.pending) - Number(m1Hours),
    );
    expect(Number(standing.available)).toBe(
      Number(standingBefore.available) + Number(m1Hours),
    );
    await openDashboard(page);
    const card = timeOffCard(page);
    await expect(stat(card, "Pending")).toContainText(`${standing.pending}h`);
    await expect(stat(card, "Available")).toContainText(
      `${standing.available}h`,
    );
  });

  test("somebody leave does not cover is told so on My Leave and Balance history", async ({
    as,
  }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    await page.goto("/leave/requests");
    await expect(
      page.getByText("Leave isn't tracked for your account."),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("My requests", { exact: true })).toHaveCount(0);
    await expect(page.locator("li", { hasText: "E2E " })).toHaveCount(0);

    await page.goto("/leave/balance-history");
    await expect(
      page.getByText("Leave isn't tracked for your account."),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Total on record")).toHaveCount(0);
  });
});
