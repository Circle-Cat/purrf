import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useState } from "react";
import Dashboard from "@/pages/Dashboard";
import { Group } from "@/constants/Groups";
import DateRangePicker from "@/components/common/DateRangePicker";
import { getSummary } from "@/api/dashboardApi";
import "@testing-library/jest-dom/vitest";

vi.mock("@/components/common/DateRangePicker", () => {
  return {
    default: vi.fn(({ onChange, defaultStartDate, defaultEndDate }) => {
      const [startDate, setStartDate] = useState(defaultStartDate);
      const [endDate, setEndDate] = useState(defaultEndDate);

      const handleDateChange = (newDate) => {
        const updatedStartDate = newDate.startDate ?? startDate;
        const updatedEndDate = newDate.endDate ?? endDate;

        setStartDate(updatedStartDate);
        setEndDate(updatedEndDate);

        onChange({ startDate: updatedStartDate, endDate: updatedEndDate });
      };

      return (
        <div data-testid="mock-date-range-picker">
          <input
            data-testid="start-date-input"
            defaultValue={startDate}
            onChange={(e) => handleDateChange({ startDate: e.target.value })}
          />
          <input
            data-testid="end-date-input"
            defaultValue={endDate}
            onChange={(e) => handleDateChange({ endDate: e.target.value })}
          />
        </div>
      );
    }),
  };
});

vi.mock("@/api/dashboardApi", () => ({
  getSummary: vi.fn(),
}));

const MOCK_TODAY = new Date("2024-02-15");
const MOCK_FIRST_OF_MONTH = new Date("2024-02-01");
const formatDate = (date) => date.toISOString().split("T")[0];

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    const date = new Date(MOCK_TODAY);
    vi.setSystemTime(date);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    afterEach(cleanup);
  });

  it("renders with correct initial state and default values", () => {
    render(<Dashboard />);

    expect(screen.getByText("Welcome")).toBeInTheDocument();

    expect(DateRangePicker).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultStartDate: formatDate(MOCK_FIRST_OF_MONTH),
        defaultEndDate: formatDate(MOCK_TODAY),
        onChange: expect.any(Function),
      }),
      undefined,
    );

    expect(screen.getByLabelText(Group.Interns)).toBeChecked();
    expect(screen.getByLabelText(Group.Employees)).not.toBeChecked();
    expect(screen.getByLabelText(Group.Volunteers)).not.toBeChecked();
    expect(
      screen.getByLabelText("Include Terminated Members"),
    ).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("updates group selection when checkboxes are clicked", () => {
    render(<Dashboard />);

    const internsCheckbox = screen.getByLabelText(Group.Interns);
    const employeesCheckbox = screen.getByLabelText(Group.Employees);
    const volunteersCheckbox = screen.getByLabelText(Group.Volunteers);

    fireEvent.click(internsCheckbox);
    fireEvent.click(employeesCheckbox);
    fireEvent.click(volunteersCheckbox);

    expect(internsCheckbox).not.toBeChecked();
    expect(employeesCheckbox).toBeChecked();
    expect(volunteersCheckbox).toBeChecked();
  });

  it("toggles 'Include Terminated Members' checkbox on click", () => {
    render(<Dashboard />);
    const terminatedCheckbox = screen.getByLabelText(
      "Include Terminated Members",
    );

    fireEvent.click(terminatedCheckbox);
    expect(terminatedCheckbox).toBeChecked();

    fireEvent.click(terminatedCheckbox);
    expect(terminatedCheckbox).not.toBeChecked();
  });

  it("calls search handler with default filter state when search button is clicked", () => {
    render(<Dashboard />);

    const searchButton = screen.getByRole("button", { name: "Search" });
    fireEvent.click(searchButton);

    expect(getSummary).toHaveBeenCalled();
  });

  it("updates date range via DateRangePicker and calls search with updated dates", () => {
    getSummary.mockResolvedValue({ data: "mocked data" });

    render(<Dashboard />);

    const startDateInput = screen.getByTestId("start-date-input");
    const endDateInput = screen.getByTestId("end-date-input");
    const searchButton = screen.getByRole("button", { name: "Search" });

    const newStartDate = "2023-12-01";
    const newEndDate = "2023-12-31";

    fireEvent.change(startDateInput, { target: { value: newStartDate } });
    fireEvent.change(endDateInput, { target: { value: newEndDate } });
    fireEvent.click(searchButton);

    expect(getSummary).toHaveBeenCalledWith({
      startDate: newStartDate,
      endDate: newEndDate,
      groups: [Group.Interns],
      includeTerminated: false,
    });
  });

  it("calls search handler with updated filter state after user interaction", () => {
    getSummary.mockResolvedValue({ data: "mocked data" });

    render(<Dashboard />);

    fireEvent.click(screen.getByLabelText(Group.Employees));
    fireEvent.click(screen.getByLabelText("Include Terminated Members"));

    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(getSummary).toHaveBeenCalledWith({
      startDate: formatDate(MOCK_FIRST_OF_MONTH),
      endDate: formatDate(MOCK_TODAY),
      groups: [Group.Interns, Group.Employees],
      includeTerminated: true,
    });
  });
});
