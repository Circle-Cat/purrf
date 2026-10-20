import { test, expect } from "../../fixtures.js";
import {
  beijingYear,
  needLeaveSeed,
  openDashboard,
  pendingFor,
  rowsOf,
  segmentsOf,
  standingOf,
  stat,
  timeOffCard,
} from "./helpers.js";

// The Time off card on the Personal Dashboard. e2e-member is covered by its
// seeded ledger rows (+60 opening, -12 this year) with M1, M2 (8 h each) and
// M5 (4 h) waiting; e2e-reviewer is not covered but has requests filed
// against it; the other accounts are neither.

test.describe("time off card", { tag: "@leave" }, () => {
  test("a covered member sees what they can spend and the ways in", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    await openDashboard(page);
    const standing = standingOf(page.account.userId);
    expect(
      Number(standing.pending),
      "the seed leaves paid requests of the member's waiting",
    ).toBeGreaterThan(0);
    const card = timeOffCard(page);
    await expect(card).toBeVisible();
    await expect(stat(card, "Available")).toContainText(
      `${standing.available}h`,
    );
    await expect(stat(card, "Available")).toContainText(
      `${(Number(standing.available) / 8).toFixed(1)} days`,
    );
    await expect(stat(card, "Pending")).toContainText(`${standing.pending}h`);
    await expect(stat(card, "Used")).toContainText(`${standing.used}h`);
    for (const name of [
      "Request time off",
      "Company holidays",
      "My requests",
      "Balance history",
    ]) {
      await expect(card.getByRole("button", { name })).toBeVisible();
    }
    await expect(card.getByRole("button", { name: /^Approvals/ })).toHaveCount(
      0,
    );
    await expect(card).not.toContainText("Leave isn't tracked");
  });

  test("an approver outside the leave population gets only approvals and holidays", async ({
    as,
  }) => {
    const page = await as("reviewer");
    needLeaveSeed(page);
    const waiting = pendingFor(page.account.userId);
    expect(
      waiting,
      "the seed leaves requests waiting on the reviewer",
    ).toBeGreaterThan(0);
    await openDashboard(page);
    const card = timeOffCard(page);
    await expect(card).toContainText("Leave isn't tracked for your account.");
    await expect(
      card.getByRole("button", { name: `Approvals (${waiting})`, exact: true }),
    ).toBeVisible();
    await expect(
      card.getByRole("button", { name: "Company holidays" }),
    ).toBeVisible();
    for (const name of ["Request time off", "My requests", "Balance history"]) {
      await expect(card.getByRole("button", { name })).toHaveCount(0);
    }
    await expect(card.getByText("Available", { exact: true })).toHaveCount(0);
    await card.getByRole("button", { name: /^Approvals/ }).click();
    await expect(page).toHaveURL(/\/leave\/approvals$/);
    await expect(
      page.getByRole("heading", { name: "Leave Approvals" }),
    ).toBeVisible();
  });

  for (const role of ["reviewer2", "readonly", "admin"]) {
    test(`${role}, neither covered nor an approver, gets no card and no request list`, async ({
      as,
    }) => {
      const page = await as(role);
      needLeaveSeed(page);
      const listed = [];
      page.on("request", (req) => {
        if (
          req.method() === "GET" &&
          new URL(req.url()).pathname === "/api/leave/requests"
        )
          listed.push(req.url());
      });
      await openDashboard(page);
      await expect(page.getByText("Time off", { exact: true })).toHaveCount(0);
      expect(listed, "nobody uncovered asks for their own requests").toEqual(
        [],
      );
    });
  }

  test("Company holidays lists the entered years with their segments", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    const entered = rowsOf(
      "SELECT DISTINCT year FROM leave_holiday ORDER BY year",
    ).map(([y]) => Number(y));
    const thisYear = beijingYear();
    const years = [...new Set([...entered, thisYear, thisYear + 1])].sort();
    expect(years).toEqual(expect.arrayContaining([2019, 2099]));

    await openDashboard(page);
    await timeOffCard(page)
      .getByRole("button", { name: "Company holidays" })
      .click();
    const dialog = page.getByRole("dialog", { name: "Company holidays" });
    const picker = dialog.getByLabel("Year");
    await expect(picker).toHaveValue(String(thisYear));
    await expect(picker.locator("option")).toHaveText(years.map(String));

    const thisYearSegments = segmentsOf(thisYear);
    if (thisYearSegments.length === 0) {
      await expect(dialog).toContainText(
        `No holidays have been entered for ${thisYear} yet.`,
      );
    } else {
      const entries = dialog.locator("li");
      await expect(entries).toHaveCount(thisYearSegments.length);
      for (const [at, { name, days }] of thisYearSegments.entries()) {
        await expect(entries.nth(at)).toContainText(name);
        await expect(entries.nth(at)).toContainText(
          ` · ${days} ${days === 1 ? "day" : "days"}`,
        );
      }
    }

    await picker.selectOption("2099");
    const labour = dialog
      .locator("li")
      .filter({ hasText: "E2E Labour Day 2099" });
    const exchange = dialog
      .locator("li")
      .filter({ hasText: "E2E Exchange Day 2099" });
    await expect(labour).toContainText("May 1 – May 5, 2099 · 5 days");
    await expect(labour.getByText("Exchangeable")).toHaveCount(0);
    await expect(exchange).toContainText("Jun 2, 2099 · 1 day");
    await expect(exchange.getByText("Exchangeable")).toBeVisible();
    await expect(dialog.locator("li")).toHaveCount(2);
  });
});
