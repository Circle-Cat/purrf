import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import BalanceHistoryRow from "@/pages/Leave/BalanceHistoryPage/components/BalanceHistoryRow";

vi.mock("@/constants/LeaveRequest", () => ({
  ENTRY_TYPE_LABELS: {
    accrual: "Annual accrual",
    deduction: "Paid leave",
    exchange: "Holiday exchange",
    adjustment: "Manual adjustment",
    carryover: "Carryover",
  },
}));

vi.mock("@/pages/Leave/utils/leaveDates", () => ({
  formatBusinessDate: vi.fn((date) => {
    const d = new Date(date);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }),
}));

const entry = (overrides = {}) => ({
  entryId: 1,
  entryType: "accrual",
  hours: "40.00",
  effectiveDate: "2026-01-01",
  note: "Annual accrual for 2026",
  ...overrides,
});

describe("BalanceHistoryRow", () => {
  it("renders the entry type label the server mapped", () => {
    render(<BalanceHistoryRow entry={entry()} />);

    expect(screen.getByText("Annual accrual")).toBeInTheDocument();
  });

  it("falls back to raw entryType when no label mapping exists", () => {
    render(<BalanceHistoryRow entry={entry({ entryType: "unknown_type" })} />);

    expect(screen.getByText("unknown_type")).toBeInTheDocument();
  });

  it("renders the note when provided", () => {
    render(<BalanceHistoryRow entry={entry()} />);

    expect(screen.getByText("Annual accrual for 2026")).toBeInTheDocument();
  });

  it("does not render a note paragraph when note is absent", () => {
    render(<BalanceHistoryRow entry={entry({ note: null })} />);

    expect(screen.getByText("Annual accrual")).toBeInTheDocument();
    expect(screen.queryByText(/Annual accrual for/)).not.toBeInTheDocument();
  });

  it("prefixes positive hours with a plus sign", () => {
    render(<BalanceHistoryRow entry={entry({ hours: "40.00" })} />);

    expect(screen.getByText(/\+40\.00\s*h/)).toBeInTheDocument();
  });

  it("renders negative hours without a prefix sign", () => {
    render(<BalanceHistoryRow entry={entry({ hours: "-8.00" })} />);

    expect(screen.getByText(/-8\.00\s*h/)).toBeInTheDocument();
  });

  it("renders zero hours without a sign prefix", () => {
    render(<BalanceHistoryRow entry={entry({ hours: "0.00" })} />);

    expect(screen.getByText(/\b0\.00\s*h\b/)).toBeInTheDocument();
  });

  it("colors positive hours emerald", () => {
    render(<BalanceHistoryRow entry={entry({ hours: "40.00" })} />);

    const signSpan = screen.getByText(/\+40\.00\s*h/);
    expect(signSpan).toHaveClass("text-emerald-700");
  });

  it("colors negative hours rose", () => {
    render(<BalanceHistoryRow entry={entry({ hours: "-8.00" })} />);

    const signSpan = screen.getByText(/-8\.00\s*h/);
    expect(signSpan).toHaveClass("text-rose-600");
  });

  it("colors zero hours muted", () => {
    render(<BalanceHistoryRow entry={entry({ hours: "0.00" })} />);

    const signSpan = screen.getByText(/\b0\.00\s*h\b/);
    expect(signSpan).toHaveClass("text-muted-foreground");
  });

  it("formats the effective date through the shared formatter", () => {
    render(
      <BalanceHistoryRow entry={entry({ effectiveDate: "2026-08-15" })} />,
    );

    expect(screen.getByText(/Aug 15, 2026/)).toBeInTheDocument();
  });

  it("renders as a list item", () => {
    const { container } = render(<BalanceHistoryRow entry={entry()} />);

    expect(container.querySelector("li")).toBeInTheDocument();
  });

  it("handles null hours gracefully", () => {
    render(<BalanceHistoryRow entry={entry({ hours: null })} />);

    const signSpan = screen.getByText(
      (_, element) => element?.textContent?.trim() === "0.00 h",
    );
    expect(signSpan).toBeInTheDocument();
    expect(signSpan).toHaveClass("text-muted-foreground");
  });

  it("handles undefined hours gracefully", () => {
    render(<BalanceHistoryRow entry={entry({ hours: undefined })} />);

    const signSpan = screen.getByText(
      (_, element) => element?.textContent?.trim() === "0.00 h",
    );
    expect(signSpan).toBeInTheDocument();
    expect(signSpan).toHaveClass("text-muted-foreground");
  });

  it("renders deduction entries with correct sign and color", () => {
    render(
      <BalanceHistoryRow
        entry={entry({
          entryType: "deduction",
          hours: "-8.00",
          note: "Paid leave Aug 13-15",
        })}
      />,
    );

    expect(screen.getByText("Paid leave")).toBeInTheDocument();
    const signSpan = screen.getByText(
      (_, element) => element?.textContent?.trim() === "-8.00 h",
    );
    expect(signSpan).toBeInTheDocument();
    expect(signSpan).toHaveClass("text-rose-600");
    expect(screen.getByText("Paid leave Aug 13-15")).toBeInTheDocument();
  });

  it("renders exchange entries as positive credits", () => {
    render(
      <BalanceHistoryRow
        entry={entry({
          entryType: "exchange",
          hours: "16.00",
          note: "Swapped National Day",
        })}
      />,
    );

    expect(screen.getByText("Holiday exchange")).toBeInTheDocument();
    expect(screen.getByText(/\+16\.00\s*h/)).toBeInTheDocument();
    expect(screen.getByText("Swapped National Day")).toBeInTheDocument();
  });
});
