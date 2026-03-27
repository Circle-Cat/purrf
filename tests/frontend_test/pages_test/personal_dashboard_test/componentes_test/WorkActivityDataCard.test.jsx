import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { WorkActivityDataCard } from "@/pages/PersonalDashboard/components/WorkActivityDataCard";

// mock DateRangePicker
vi.mock("@/components/common/DateRangePicker", () => ({
  default: ({ onChange }) => (
    <button
      data-testid="date-picker"
      onClick={() =>
        onChange({
          startDate: "2026-01-01",
          endDate: "2026-01-31",
        })
      }
    >
      MockDatePicker
    </button>
  ),
}));

const mockData = {
  startDate: "2026-01-01",
  endDate: "2026-01-31",
  summary: {
    jiraTickets: 5,
    mergedCLs: 3,
    mergedLOC: 1200,
    meetingHours: 10,
    chatMessages: 50,
  },
};

describe("WorkActivityDataCard", () => {
  it("should display all metrics", () => {
    render(<WorkActivityDataCard initialData={mockData} isLoading={false} />);

    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("50")).toBeInTheDocument();
  });

  it("should show loading state", () => {
    render(<WorkActivityDataCard initialData={mockData} isLoading={true} />);

    expect(screen.getByText("Loading activity data...")).toBeInTheDocument();
  });

  it("should call onSearch when clicking search button", () => {
    const onSearchMock = vi.fn();

    render(
      <WorkActivityDataCard
        initialData={mockData}
        onSearch={onSearchMock}
        isLoading={false}
      />,
    );

    fireEvent.click(screen.getByTestId("date-picker"));
    fireEvent.click(screen.getByText("Search"));

    expect(onSearchMock).toHaveBeenCalledWith({
      startDate: "2026-01-01",
      endDate: "2026-01-31",
    });
  });

  it("should disable search button when loading", () => {
    render(<WorkActivityDataCard initialData={mockData} isLoading={true} />);

    expect(screen.getByText("Search")).toBeDisabled();
  });

  it("should display 0 when summary is empty", () => {
    render(
      <WorkActivityDataCard initialData={{ summary: {} }} isLoading={false} />,
    );

    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBeGreaterThan(0);
  });
});
