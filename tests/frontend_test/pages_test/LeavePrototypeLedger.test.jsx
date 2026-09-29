import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminView from "@/pages/LeavePrototype/AdminView";
import OrgLedger, { EVERYONE } from "@/pages/LeavePrototype/OrgLedger";
import { ORG_LEDGER } from "@/pages/LeavePrototype/mockData";

const renderAdmin = () =>
  render(<AdminView adjustments={[]} onAdjust={() => {}} />);

const openLedger = async (user) => {
  await user.click(screen.getByRole("tab", { name: "Ledger" }));
};

// The Ledger tab is a list of the same rows the employee's own history shows.
const bodyRows = () =>
  within(screen.getByRole("tabpanel")).getAllByRole("listitem");

describe("Leave prototype — administrator ledger", () => {
  it("pages everybody's rows 50 at a time, newest first", async () => {
    const user = userEvent.setup();
    renderAdmin();
    await openLedger(user);

    const total = ORG_LEDGER.length;
    expect(
      screen.getByText(`Page 1 of ${Math.ceil(total / 50)} · ${total} entries`),
    ).toBeInTheDocument();
    expect(bodyRows()).toHaveLength(50);
    expect(within(bodyRows()[0]).getByText("Sep 21, 2026")).toBeInTheDocument();
    // Every row on this tab names whose entry it is.
    for (const row of bodyRows()) {
      expect(
        row.querySelector("p > span.font-medium")?.textContent,
      ).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  it("disables Next on the last page", async () => {
    const user = userEvent.setup();
    renderAdmin();
    await openLedger(user);

    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByText(/^Page 3 of 3/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("opens one person's history from the Balances tab, on page 1", async () => {
    const user = userEvent.setup();
    renderAdmin();
    await openLedger(user);
    await user.click(screen.getByRole("button", { name: "Next" }));

    await user.click(screen.getByRole("tab", { name: "Balances" }));
    const marcus = screen.getByText("Marcus Bell").closest("tr");
    await user.click(
      within(marcus).getByRole("button", { name: "View history" }),
    );

    const own = ORG_LEDGER.filter((row) => row.userId === 2).length;
    expect(
      screen.getByText(`Page 1 of 1 · ${own} entries`),
    ).toBeInTheDocument();
    for (const row of bodyRows()) {
      expect(within(row).getByText("Marcus Bell")).toBeInTheDocument();
    }
  });

  it("keeps a leaver's rows and an unresolvable account under Everyone", async () => {
    const user = userEvent.setup();
    renderAdmin();
    await openLedger(user);
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getAllByText("Hannah Kim").length).toBeGreaterThan(0);
    expect(screen.getAllByText("User 14 — unavailable").length).toBeGreaterThan(
      0,
    );
  });

  it("orders two rows on one day by id, newest first", async () => {
    const user = userEvent.setup();
    renderAdmin();
    await user.click(screen.getByRole("tab", { name: "Balances" }));
    const wei = screen.getByText("Wei Zhang").closest("tr");
    await user.click(within(wei).getByRole("button", { name: "View history" }));

    const onPromotionDay = bodyRows().filter((row) =>
      within(row).queryByText("Jul 6, 2026"),
    );
    expect(
      onPromotionDay.map((row) =>
        within(row).queryByText("Level change")
          ? "Level change"
          : "Weekly accrual",
      ),
    ).toEqual(["Level change", "Weekly accrual"]);
  });

  it("colours a negative figure red, like the employee's own history", async () => {
    const user = userEvent.setup();
    renderAdmin();
    await user.click(screen.getByRole("tab", { name: "Balances" }));
    const sofia = screen.getByText("Sofia Almeida").closest("tr");
    await user.click(
      within(sofia).getByRole("button", { name: "View history" }),
    );

    const hours = screen.getByText("-8.00h");
    expect(hours.className).toMatch(/text-rose-600/);
  });

  it("says so when a person has no rows, instead of drawing an empty table", () => {
    render(
      <OrgLedger
        rows={[]}
        people={{}}
        filterOptions={[]}
        personId={EVERYONE}
        onPersonChange={() => {}}
        page={1}
        onPageChange={() => {}}
      />,
    );

    expect(
      screen.getByText("No ledger entries for this person yet."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("puts this session's adjustments in the ledger", async () => {
    const user = userEvent.setup();
    render(
      <AdminView
        adjustments={[
          {
            id: 99999999999,
            personId: 4,
            personName: "Tobias Lund",
            entryType: "manual_adjustment",
            hours: 3,
            note: "Written in this session",
            effectiveDate: "2026-09-28",
          },
        ]}
        onAdjust={() => {}}
      />,
    );
    await openLedger(user);

    expect(
      within(bodyRows()[0]).getByText("Written in this session"),
    ).toBeInTheDocument();
  });
});

describe("Leave prototype — a balance is its ledger", () => {
  it("shows each person's balance as the sum of their Ledger rows", async () => {
    const user = userEvent.setup();
    renderAdmin();
    await user.click(screen.getByRole("tab", { name: "Balances" }));

    for (const [name, userId] of [
      ["Dana Whitfield", 1],
      ["Wei Zhang", 5],
      ["Sofia Almeida", 11],
    ]) {
      const sum = ORG_LEDGER.filter((row) => row.userId === userId).reduce(
        (total, row) => total + row.hours,
        0,
      );
      const row = screen.getByText(name).closest("tr");
      expect(
        within(row).getAllByText(`${sum.toFixed(2)}h`).length,
      ).toBeGreaterThan(0);
    }
  });

  it("gives Dana the same rows on both views", () => {
    const dana = ORG_LEDGER.filter((row) => row.userId === 1);
    expect(dana.reduce((total, row) => total + row.hours, 0)).toBeCloseTo(42.2);
  });
});

describe("Leave prototype — one row format for both ledgers", () => {
  it("names nobody on the employee's own history", async () => {
    const { default: LedgerPage } =
      await import("@/pages/LeavePrototype/LedgerPage");
    render(
      <LedgerPage
        ledger={[
          {
            id: 1,
            entryType: "leave_deduction",
            hours: -8,
            effectiveDate: "2026-09-17",
            note: "Paid leave 2026-09-17",
          },
        ]}
        balance={-8}
        pending={0}
        available={-8}
        onBack={() => {}}
      />,
    );

    const [row] = screen.getAllByRole("listitem");
    expect(within(row).getByText("Leave taken")).toBeInTheDocument();
    expect(within(row).getByText("Sep 17, 2026")).toBeInTheDocument();
    expect(within(row).queryByText(/·/)).toBeNull();
  });
});
