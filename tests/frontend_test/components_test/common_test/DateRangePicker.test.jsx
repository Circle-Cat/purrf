import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import DateRangePicker from "@/components/common/DateRangePicker";
import "@testing-library/jest-dom/vitest";

describe("DateRangePicker", () => {
  afterEach(cleanup);

  it("renders with default empty values", () => {
    render(<DateRangePicker />);
    expect(screen.getByTestId("start-date-input")).toHaveValue("");
    expect(screen.getByTestId("end-date-input")).toHaveValue("");
  });

  it("renders with provided default dates", () => {
    const startDate = "2023-10-01";
    const endDate = "2023-10-31";
    render(
      <DateRangePicker defaultStartDate={startDate} defaultEndDate={endDate} />,
    );
    expect(screen.getByTestId("start-date-input")).toHaveValue(startDate);
    expect(screen.getByTestId("end-date-input")).toHaveValue(endDate);
  });

  it("calls onChange when the start date is changed", () => {
    const onChange = vi.fn();
    render(<DateRangePicker onChange={onChange} />);

    const startDateInput = screen.getByTestId("start-date-input");
    const newStartDate = "2023-11-15";

    fireEvent.change(startDateInput, { target: { value: newStartDate } });

    expect(startDateInput).toHaveValue(newStartDate);
    expect(onChange).toHaveBeenCalledWith({
      startDate: newStartDate,
      endDate: "",
    });
  });

  it("calls onChange when the end date is changed", () => {
    const onChange = vi.fn();
    const startDate = "2023-11-01";
    render(
      <DateRangePicker onChange={onChange} defaultStartDate={startDate} />,
    );

    const endDateInput = screen.getByTestId("end-date-input");
    const newEndDate = "2023-11-20";

    fireEvent.change(endDateInput, { target: { value: newEndDate } });

    expect(endDateInput).toHaveValue(newEndDate);
    expect(onChange).toHaveBeenCalledWith({
      startDate: startDate,
      endDate: newEndDate,
    });
  });

  it("updates the end date if the new start date is after the end date", () => {
    const onChange = vi.fn();
    render(
      <DateRangePicker
        defaultStartDate="2023-01-10"
        defaultEndDate="2023-01-15"
        onChange={onChange}
      />,
    );

    const startDateInput = screen.getByTestId("start-date-input");
    const newStartDate = "2023-01-20";

    fireEvent.change(startDateInput, { target: { value: newStartDate } });

    expect(onChange).toHaveBeenCalledWith({
      startDate: newStartDate,
      endDate: newStartDate,
    });

    expect(screen.getByTestId("end-date-input")).toHaveValue(newStartDate);
  });

  it("updates input values when default props change", () => {
    const { rerender } = render(
      <DateRangePicker defaultStartDate="2023-01-01" />,
    );
    expect(screen.getByTestId("start-date-input")).toHaveValue("2023-01-01");

    rerender(<DateRangePicker defaultStartDate="2024-02-02" />);
    expect(screen.getByTestId("start-date-input")).toHaveValue("2024-02-02");
  });

  it("sets the min attribute on the end date input based on the start date", () => {
    const startDate = "2023-05-10";
    render(<DateRangePicker defaultStartDate={startDate} />);

    const endDateInput = screen.getByTestId("end-date-input");
    expect(endDateInput).toHaveAttribute("min", startDate);
  });

  it("does not throw an error if onChange prop is not provided", () => {
    render(<DateRangePicker />);
    const startDateInput = screen.getByTestId("start-date-input");

    expect(() =>
      fireEvent.change(startDateInput, { target: { value: "2023-12-01" } }),
    ).not.toThrow();
  });
});
