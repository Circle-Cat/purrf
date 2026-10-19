import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import LedgerPage from "@/pages/Leave/LedgerPage";
import { useLeaveLedger } from "@/pages/Leave/hooks/useLeaveLedger";

vi.mock("@/pages/Leave/hooks/useLeaveLedger", () => ({
  useLeaveLedger: vi.fn(),
}));

const mockUseLeaveLedger = vi.mocked(useLeaveLedger);

describe("LeaveLedgerPage (LedgerTab)", () => {
  const mockPeople = [
    { id: 42, name: "Alice Smith", ldap: "asmith" },
    { id: 99, name: "Bob Jones", ldap: "bjones" },
  ];

  const defaultProps = {
    userId: null,
    page: 1,
    onUserChange: vi.fn(),
    onPageChange: vi.fn(),
    people: mockPeople,
  };

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
    expect(screen.getByText("All Employees")).toBeInTheDocument();
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
          entryId: 1,
          userId: 42,
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

  it("disables Previous button on the first page", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [{ entryId: 1 }],
      totalEntries: 100,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} page={1} />);

    const prevBtn = screen.getByRole("button", { name: /Previous/i });
    const nextBtn = screen.getByRole("button", { name: /Next/i });

    expect(prevBtn).toBeDisabled();
    expect(nextBtn).not.toBeDisabled();
  });

  it("triggers onPageChange when page buttons are clicked", () => {
    mockUseLeaveLedger.mockReturnValue({
      entries: [{ entryId: 1 }],
      totalEntries: 100,
      isLoading: false,
      loadError: false,
    });

    render(<LedgerPage {...defaultProps} page={1} />);

    const nextBtn = screen.getByRole("button", { name: /Next/i });
    fireEvent.click(nextBtn);

    expect(defaultProps.onPageChange).toHaveBeenCalledWith(2);
  });
});
