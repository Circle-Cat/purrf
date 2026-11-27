import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import RequestSpan from "@/pages/Leave/components/RequestSpan";

const row = (overrides = {}) => ({
  startDate: "2026-06-18",
  endDate: "2026-06-22",
  startTime: null,
  endTime: null,
  hours: "24.00",
  workdays: 3,
  daysNotCounted: [
    { date: "2026-06-21", holidayName: null },
    { date: "2026-06-22", holidayName: null },
  ],
  ...overrides,
});

describe("RequestSpan", () => {
  it("puts the working days between the dates and the hours", () => {
    render(<RequestSpan row={row()} />);

    expect(
      screen.getByText("Jun 18 – Jun 22, 2026 · 3 working days · 24.00 h"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Not counted: Jun 21 (weekend), Jun 22 (weekend)"),
    ).toBeInTheDocument();
  });

  it("leaves the count off a single day, where it would repeat the date", () => {
    render(
      <RequestSpan
        row={row({
          startDate: "2026-06-18",
          endDate: "2026-06-18",
          startTime: "09:00:00",
          endTime: "12:00:00",
          hours: "3.00",
          workdays: 1,
          daysNotCounted: [],
        })}
      />,
    );

    expect(
      screen.getByText("Jun 18, 2026 · 09:00 – 12:00 · 3.00 h"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Not counted/)).not.toBeInTheDocument();
  });

  it("shows only the hours when the server sent no breakdown", () => {
    // The server leaves the breakdown out when today's calendar no longer
    // adds up to the stored hours.
    render(<RequestSpan row={row({ workdays: null, daysNotCounted: null })} />);

    expect(
      screen.getByText("Jun 18 – Jun 22, 2026 · 24.00 h"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Not counted/)).not.toBeInTheDocument();
  });

  it("leaves the count off an exchange, whose days are holidays worked", () => {
    render(
      <RequestSpan
        row={row({
          type: "exchange",
          startDate: "2026-10-01",
          endDate: "2026-10-02",
          hours: "16.00",
          workdays: 2,
          daysNotCounted: [],
        })}
      />,
    );

    expect(
      screen.getByText("Oct 1 – Oct 2, 2026 · 16.00 h"),
    ).toBeInTheDocument();
  });
});
