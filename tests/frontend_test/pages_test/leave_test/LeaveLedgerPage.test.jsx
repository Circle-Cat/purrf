import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import LedgerPage from "@/pages/Leave/LedgerPage";
import { useLeaveLedger } from "@/pages/Leave/hooks/useLeaveLedger";
import { LEAVE_CALENDAR_ZONE_LABEL } from "@/pages/Leave/utils/leaveDates";

vi.mock("@/pages/Leave/hooks/useLeaveLedger", () => ({
  useLeaveLedger: vi.fn(),
}));

const mockUseLeaveLedger = vi.mocked(useLeaveLedger);

describe("LeaveLedgerPage (LedgerTab)", () => {
  const mockPeople = [
    { id: 42, userId: 42, name: "Alice Smith", ldap: "asmith" },
    { id: 99, userId: 43, name: "Bob Jones", ldap: "bjones" },
  ];

  const defaultProps = {
    userId: null,
    page: 1,
    onUserChange: vi.fn(),
    onPageChange: vi.fn(),
    people: mockPeople,
  };

  const sampleEntries = [
    {
      leaveLedgerId: 1,
      userId: 42,
      name: "Alice Smith",
      ldap: "asmith",
      hours: "40.00",
      entryType: "weekly_accrual",
      effectiveDate: "2026-01-01",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders person select dropdown with all options", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [],
      totalEntries: 0,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} />);

    const select = screen.getByLabelText(/Filter by Person/i);
    expect(select).toBeInTheDocument();
    expect(screen.getByText("All employees")).toBeInTheDocument();
    expect(screen.getByText("Alice Smith (asmith)")).toBeInTheDocument();
    expect(screen.getByText("Bob Jones (bjones)")).toBeInTheDocument();
  });

  it("calls onUserChange when a user selection changes", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [],
      totalEntries: 0,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} />);

    const select = screen.getByLabelText(/Filter by Person/i);
    fireEvent.change(select, { target: { value: "42" } });

    expect(defaultProps.onUserChange).toHaveBeenCalledWith(42);
  });

  it("passes props to useLeaveLedger hook correctly", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [],
      totalEntries: 0,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} userId={42} page={2} />);

    expect(mockUseLeaveLedger).toHaveBeenCalledWith({
      userId: 42,
      page: 2,
      pageSize: 50,
    });
  });

  it("renders loading indicator when isLoading is true", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [],
      totalEntries: 0,
      isLoading: true,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} />);
    expect(screen.getByText(/Loading ledger entries/i)).toBeInTheDocument();
  });

  it("renders empty message when no entries exist", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [],
      totalEntries: 0,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} />);
    expect(
      screen.getByText(/No balance history entries found/i),
    ).toBeInTheDocument();
  });

  it("renders ledger entries list using BalanceHistoryRow", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [
        {
          leaveLedgerId: 1,
          userId: 42,
          name: "Alice Smith",
          ldap: "asmith",
          hours: "40.00",
          entryType: "weekly_accrual",
          effectiveDate: "2026-01-01",
        },
      ],
      totalEntries: 1,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} />);

    const list = screen.getByRole("list");

    expect(within(list).getByText(/Alice Smith/i)).toBeInTheDocument();
    expect(screen.getByText(/\+40\.00\s*h/)).toBeInTheDocument();
  });

  it("renders ledger entries for former employees not in people list", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [
        {
          leaveLedgerId: 2,
          userId: 888,
          name: "Charlie Former",
          ldap: "cformer",
          hours: "-8.00",
          entryType: "leave_deduction",
          effectiveDate: "2026-02-01",
        },
      ],
      totalEntries: 1,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} />);

    const list = screen.getByRole("list");

    expect(within(list).getByText(/Charlie Former/i)).toBeInTheDocument();
    expect(within(list).getByText(/cformer/i)).toBeInTheDocument();
  });

  it("shows 1–50 of 120 and disables Prev on the first page", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: sampleEntries,
      totalEntries: 120,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} page={1} />);

    expect(screen.getByText("1–50 of 120")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/i })).not.toBeDisabled();
  });

  it("shows 51–100 of 120 and enables both Prev and Next on a middle page", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: sampleEntries,
      totalEntries: 120,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} page={2} />);

    expect(screen.getByText("51–100 of 120")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Prev/i })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/i })).not.toBeDisabled();
  });

  it("shows 101–120 of 120 and disables Next on a partial last page", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: sampleEntries,
      totalEntries: 120,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} page={3} />);

    expect(screen.getByText("101–120 of 120")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Prev/i })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/i })).toBeDisabled();
  });

  it("shows 0–0 of 0, disables pagination, and renders empty state message when there are no entries", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [],
      totalEntries: 0,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} page={1} />);

    expect(screen.getByText("0–0 of 0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/i })).toBeDisabled();
    expect(
      screen.getByText(/No balance history entries found/i),
    ).toBeInTheDocument();
  });

  it("displays calendar zone label and removes 'Showing' text", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: sampleEntries,
      totalEntries: 120,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} />);

    expect(screen.getByText(LEAVE_CALENDAR_ZONE_LABEL)).toBeInTheDocument();
    expect(screen.queryByText(/Showing/i)).not.toBeInTheDocument();
  });

  it("clicking Prev and Next on page 2 calls onPageChange with correct values", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: sampleEntries,
      totalEntries: 120,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} page={2} />);

    fireEvent.click(screen.getByRole("button", { name: /Prev/i }));
    expect(defaultProps.onPageChange).toHaveBeenLastCalledWith(1);

    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    expect(defaultProps.onPageChange).toHaveBeenLastCalledWith(3);
  });
});
