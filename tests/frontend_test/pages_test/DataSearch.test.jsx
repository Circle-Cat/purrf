import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useState } from "react";
import "@testing-library/jest-dom/vitest";
import DataSearch from "@/pages/DataSearch";
import DateRangePicker from "@/components/common/DateRangePicker";

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

describe("DataSearch", () => {
  it("renders the DataSearch component correctly", () => {
    render(<DataSearch />);

    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
    expect(screen.getByText("Data Search Page")).toBeInTheDocument();

    expect(DateRangePicker).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultStartDate: "",
        defaultEndDate: "",
        onChange: expect.any(Function),
      }),
      undefined,
    );
  });

  it("updates date range via DateRangePicker", () => {
    render(<DataSearch />);

    const startDateInput = screen.getByTestId("start-date-input");
    const endDateInput = screen.getByTestId("end-date-input");

    const newStartDate = "2024-10-01";
    const newEndDate = "2025-09-19";

    fireEvent.change(startDateInput, { target: { value: newStartDate } });
    expect(startDateInput.value).toBe(newStartDate);

    fireEvent.change(endDateInput, { target: { value: newEndDate } });
    expect(endDateInput.value).toBe(newEndDate);
  });
});
