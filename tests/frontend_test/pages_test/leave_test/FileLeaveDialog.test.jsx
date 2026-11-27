import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import FileLeaveDialog from "@/pages/Leave/components/FileLeaveDialog";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

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
    api.previewLeaveRequest.mockResolvedValue({
      success: true,
      message: "ok",
      data: { hours: "24.00", workdays: 3, daysNotCounted: [] },
    });
  });

  it("shows what the dates come to before anything is submitted", async () => {
    api.previewLeaveRequest.mockResolvedValue({
      success: true,
      message: "ok",
      data: {
        hours: "40.00",
        workdays: 5,
        daysNotCounted: [
          { date: "2026-12-25", holidayName: "QA holiday" },
          { date: "2026-12-27", holidayName: null },
          { date: "2026-12-28", holidayName: null },
        ],
      },
    });
    const onSubmit = open();

    setDates("2026-12-22", "2026-12-29");

    expect(
      await screen.findByText(
        "Dec 22 – Dec 29, 2026 · 5 working days · 40.00 h",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Not counted: Dec 25 (QA holiday), Dec 27 (weekend), Dec 28 (weekend)",
      ),
    ).toBeInTheDocument();
    expect(api.previewLeaveRequest).toHaveBeenCalledWith({
      type: "paid",
      startDate: "2026-12-22",
      endDate: "2026-12-29",
      startTime: null,
      endTime: null,
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows why the dates cannot be filed before Submit is pressed", async () => {
    api.previewLeaveRequest.mockRejectedValue({
      response: {
        data: {
          message:
            "Those days are already time off, so there is nothing to request.",
        },
      },
    });
    open();

    setDates("2026-12-27", "2026-12-28");

    expect(
      await screen.findByText(
        "Those days are already time off, so there is nothing to request.",
      ),
    ).toBeInTheDocument();
  });

  it("asks nothing until both dates make sense", async () => {
    open();

    fireEvent.change(screen.getByLabelText("First day"), {
      target: { value: "2026-12-22" },
    });
    await new Promise((resolve) => setTimeout(resolve, 500));

    expect(api.previewLeaveRequest).not.toHaveBeenCalled();
  });

  it("says who will read the request before it is filed", () => {
    open({ approverName: "Jasmine Li", approverLdap: "jasmine" });

    expect(
      screen.getByText(
        "Your request goes to Jasmine Li (jasmine) for approval.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  it("shows why nobody can approve it, and will not submit", () => {
    const onSubmit = open({
      approverProblem:
        "Your manager (jasmine) has no purrf account, so they cannot approve anything yet.",
    });
    setDates("2026-10-01", "2026-10-03");

    expect(
      screen.getByText(/Your manager \(jasmine\) has no purrf account/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("says nothing about the approver before it is known", () => {
    open();

    expect(screen.queryByText(/for approval/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
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

  it("offers only half-hour times, the steps the server takes leave in", () => {
    open();
    setDates("2026-10-01", "2026-10-01");

    for (const label of ["From (optional)", "To (optional)"]) {
      const choices = Array.from(
        screen.getByLabelText(label).querySelectorAll("option"),
        (option) => option.value,
      );
      // A blank for "no times", then every half hour of the day.
      expect(choices).toHaveLength(49);
      expect(choices[0]).toBe("");
      expect(choices.slice(1, 4)).toEqual(["00:00", "00:30", "01:00"]);
      expect(choices.at(-1)).toBe("23:30");
      expect(choices).not.toContain("16:20");
    }
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

  /**
   * Renders the dialog the way its parent drives it: a refused submit comes
   * back as false, and the refusal then arrives as `saveError`.
   */
  const renderRefused = () => {
    const refusal = "Your Azure record has no manager.";
    const props = {
      isSaving: false,
      onClose: vi.fn(),
      onSubmit: vi.fn().mockResolvedValue(false),
    };
    const view = render(<FileLeaveDialog isOpen saveError={null} {...props} />);
    const rerenderWith = (overrides) =>
      view.rerender(
        <FileLeaveDialog
          isOpen
          saveError={refusal}
          {...props}
          {...overrides}
        />,
      );
    return { refusal, props, rerenderWith };
  };

  it("shows the server's refusal of a submit", async () => {
    const { refusal, props, rerenderWith } = renderRefused();
    setDates("2026-10-01", "2026-10-01");
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(props.onSubmit).toHaveBeenCalled());

    rerenderWith({});

    expect(screen.getByText(refusal)).toBeInTheDocument();
  });

  it("does not show a refusal left over from before it was opened", () => {
    // The refusal belongs to the hook the parent shares, and outlives the
    // dialog that caused it.
    open({ saveError: "Your Azure record has no manager." });

    expect(
      screen.queryByText("Your Azure record has no manager."),
    ).not.toBeInTheDocument();
  });

  it("starts clean when opened again after a refusal", async () => {
    const { refusal, props, rerenderWith } = renderRefused();
    setDates("2026-10-01", "2026-10-01");
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(props.onSubmit).toHaveBeenCalled());
    rerenderWith({});
    expect(screen.getByText(refusal)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    rerenderWith({ isOpen: false });
    rerenderWith({ isOpen: true });

    expect(screen.queryByText(refusal)).not.toBeInTheDocument();
  });
});
