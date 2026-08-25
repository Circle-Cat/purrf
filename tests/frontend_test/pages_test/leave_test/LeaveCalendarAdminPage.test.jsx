import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import LeaveCalendarAdminPage from "@/pages/Leave/CalendarAdminPage";
import * as api from "@/api/leaveApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

vi.mock("@/api/leaveApi");
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

const envelope = (data) => ({ success: true, message: "ok", data });

const segment = (overrides = {}) => ({
  name: "National Day",
  startDate: "2026-10-01",
  endDate: "2026-10-03",
  dayCount: 3,
  isExchangeable: true,
  ...overrides,
});

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/leave/calendar"]}>
      <Routes>
        <Route path="/leave/calendar" element={<LeaveCalendarAdminPage />} />
        <Route path="/dashboard/me" element={<p>Personal dashboard</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe("LeaveCalendarAdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true });
    api.getLeaveHolidayYears.mockResolvedValue(
      envelope({ years: [2026], currentYear: 2026, nextYear: 2027 }),
    );
    api.getLeaveHolidays.mockResolvedValue(
      envelope({ year: 2026, totalDays: 3, segments: [segment()] }),
    );
    api.replaceLeaveHolidays.mockResolvedValue(
      envelope({ year: 2026, totalDays: 3, segments: [segment()] }),
    );
  });

  it("shows the year as entered, with its day count", async () => {
    renderPage();

    await waitFor(() =>
      expect(screen.getByDisplayValue("National Day")).toBeInTheDocument(),
    );
    expect(screen.getByText(/2026 — 1 holidays, 3 days/)).toBeInTheDocument();
  });

  it("says what an empty year would do, rather than looking blank", async () => {
    api.getLeaveHolidays.mockResolvedValue(
      envelope({ year: 2026, totalDays: 0, segments: [] }),
    );

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/refuses every leave request dated in it/i),
      ).toBeInTheDocument(),
    );
  });

  it("cannot be saved until something changes", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByDisplayValue("National Day")).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("button", { name: "Save the year" }),
    ).toBeDisabled();
  });

  it("says the whole year is being replaced before it happens", async () => {
    // Saving replaces the year, so a removed holiday is deleted. That is said
    // in advance rather than reported afterwards.
    renderPage();
    await waitFor(() =>
      expect(screen.getByDisplayValue("National Day")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    fireEvent.click(screen.getByRole("button", { name: "Save the year" }));

    expect(screen.getByText("Replace all of 2026?")).toBeInTheDocument();
    expect(
      screen.getByText(/Anything you removed is deleted/),
    ).toBeInTheDocument();
    expect(api.replaceLeaveHolidays).not.toHaveBeenCalled();
  });

  it("saves nothing if the confirmation is dismissed", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByDisplayValue("National Day")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Add a holiday" }));
    fireEvent.click(screen.getByRole("button", { name: "Save the year" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(api.replaceLeaveHolidays).not.toHaveBeenCalled();
  });

  it("saves the year once confirmed", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByDisplayValue("National Day")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    fireEvent.click(screen.getByRole("button", { name: "Save the year" }));
    fireEvent.click(screen.getByRole("button", { name: "Replace 2026" }));

    await waitFor(() => expect(api.replaceLeaveHolidays).toHaveBeenCalled());
    expect(api.replaceLeaveHolidays.mock.calls[0][1]).toEqual([]);
  });

  it("shows the server's refusal naming the holiday at fault", async () => {
    api.replaceLeaveHolidays.mockRejectedValue(
      Object.assign(new Error("Request failed"), {
        response: {
          data: { message: "National Day ends before it starts." },
        },
      }),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByDisplayValue("National Day")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Add a holiday" }));
    fireEvent.click(screen.getByRole("button", { name: "Save the year" }));
    fireEvent.click(screen.getByRole("button", { name: "Replace 2026" }));

    await waitFor(() =>
      expect(
        screen.getByText("National Day ends before it starts."),
      ).toBeInTheDocument(),
    );
  });

  it("carries exchangeable as one flag for the whole holiday", async () => {
    // Not a choice per day. Which days somebody trades is their decision at
    // request time, and the calendar does not record it.
    renderPage();
    await waitFor(() =>
      expect(screen.getByDisplayValue("National Day")).toBeInTheDocument(),
    );

    const boxes = screen.getAllByLabelText("Exchangeable");
    expect(boxes).toHaveLength(1);
  });
});
