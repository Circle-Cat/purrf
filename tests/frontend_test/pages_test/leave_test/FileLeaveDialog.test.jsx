import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import FileLeaveDialog from "@/pages/Leave/components/FileLeaveDialog";

const open = (props = {}) => {
  const onSubmit = vi.fn().mockResolvedValue(true);
  render(
    <FileLeaveDialog
      isOpen
      isSaving={false}
      saveError={null}
      onClose={vi.fn()}
      onSubmit={onSubmit}
      {...props}
    />,
  );
  return onSubmit;
};

const setDates = (first, last) => {
  fireEvent.change(screen.getByLabelText("First day"), {
    target: { value: first },
  });
  fireEvent.change(screen.getByLabelText("Last day"), {
    target: { value: last },
  });
};

describe("FileLeaveDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends the dates as the strings the inputs hold", async () => {
    // A native date input's value is already `YYYY-MM-DD`, which is what the
    // API takes. Building a Date from it renders 1 October as 30 September
    // west of UTC.
    const onSubmit = open();
    setDates("2026-10-01", "2026-10-03");

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      startDate: "2026-10-01",
      endDate: "2026-10-03",
    });
  });

  it("offers no times on a range, because a range is always whole days", () => {
    open();
    setDates("2026-10-01", "2026-10-03");

    expect(screen.queryByLabelText("From (optional)")).not.toBeInTheDocument();
  });

  it("offers times on a single day", () => {
    open();
    setDates("2026-10-01", "2026-10-01");

    expect(screen.getByLabelText("From (optional)")).toBeInTheDocument();
  });

  it("offers no times on an exchange, which is always whole days", () => {
    open();
    setDates("2026-10-01", "2026-10-01");
    fireEvent.change(screen.getByLabelText("Type"), {
      target: { value: "exchange" },
    });

    expect(screen.queryByLabelText("From (optional)")).not.toBeInTheDocument();
  });

  it("sends nothing for times that were left blank", async () => {
    // The server refuses times where they cannot apply rather than ignoring
    // them, so an empty string must not be sent as one.
    const onSubmit = open();
    setDates("2026-10-01", "2026-10-01");

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      startTime: null,
      endTime: null,
    });
  });

  it("sends both times when both are given", async () => {
    const onSubmit = open();
    setDates("2026-10-01", "2026-10-01");
    fireEvent.change(screen.getByLabelText("From (optional)"), {
      target: { value: "09:00" },
    });
    fireEvent.change(screen.getByLabelText("To (optional)"), {
      target: { value: "13:30" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      startTime: "09:00",
      endTime: "13:30",
    });
  });

  it("refuses one time on its own", () => {
    const onSubmit = open();
    setDates("2026-10-01", "2026-10-01");
    fireEvent.change(screen.getByLabelText("From (optional)"), {
      target: { value: "09:00" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(screen.getByText(/both times, or neither/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("refuses a last day before the first", () => {
    const onSubmit = open();
    setDates("2026-10-03", "2026-10-01");

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(screen.getByText(/cannot come before/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("leaves every business rule to the server", () => {
    // A date in the past, an overlap, a year with no calendar, notice that
    // falls short: all refused server-side and shown in its own words. This
    // dialog must not grow a second copy of any of them.
    const onSubmit = open();
    setDates("2020-01-01", "2020-01-01");

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(onSubmit).toHaveBeenCalled();
  });

  it("shows the server's refusal", () => {
    open({ saveError: "Your Azure record has no manager." });

    expect(
      screen.getByText("Your Azure record has no manager."),
    ).toBeInTheDocument();
  });
});
