import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InterviewMeetingDialog from "@/pages/Recruiting/applications/InterviewMeetingDialog";

// Mock TimezoneSelector to simplify option interaction in JSDOM, following
// the established convention (see MeetingManagementDialog.test.jsx). The
// real TimezoneSelector's onChange receives a react-select option object
// ({value, label}); this mock reproduces that shape rather than passing the
// raw string, so a test that reads `onChange`'s first argument as a string
// instead of unwrapping `.value` would fail here.
vi.mock("@/components/common/TimezoneSelector", () => ({
  default: ({ value, onChange }) => (
    <select
      data-testid="timezone-selector"
      value={value}
      onChange={(e) => onChange({ value: e.target.value })}
    >
      <option value="America/Los_Angeles">Pacific Time (US &amp; Canada)</option>
      <option value="America/New_York">Eastern Time (US &amp; Canada)</option>
    </select>
  ),
}));

const POOL = [
  { userId: 10, name: "Eve Evaluator", email: "eve@example.com" },
  { userId: 11, name: "Ivan Interviewer", email: "ivan@example.com" },
];

const INTERVIEW = {
  interviewId: 7,
  stage: "behavioral",
  round: 1,
  startAt: "2026-08-05T21:00:00Z",
  endAt: "2026-08-05T21:45:00Z",
  timezone: "America/Los_Angeles",
  meetLink: "https://meet.google.com/abc-defg-hij",
  assigneeId: 10,
  assigneeName: "Eve Evaluator",
  scheduledByName: "Jane Smith",
};

/**
 * Pick an interviewer via the shared PeoplePicker (shadcn Select) dropdown.
 * Radix also renders a visually-hidden native <select> fallback with
 * matching <option> text for form semantics, so the option must be looked
 * up scoped to the open listbox rather than via a document-wide query.
 */
const pickInterviewer = async (user, label) => {
  await user.click(screen.getByRole("combobox", { name: "Interviewer" }));
  const listbox = await screen.findByRole("listbox");
  await user.click(within(listbox).getByText(label));
};

const renderDialog = (props = {}) => {
  const onSubmit = vi.fn();
  const onOpenChange = vi.fn();
  const utils = render(
    <InterviewMeetingDialog
      open
      onOpenChange={onOpenChange}
      mode="schedule"
      interview={null}
      defaultAssigneeId={null}
      interviewPool={POOL}
      onSubmit={onSubmit}
      submitting={false}
      {...props}
    />,
  );
  return { ...utils, onSubmit, onOpenChange };
};

describe("InterviewMeetingDialog", () => {
  it("defaults to 45 minutes and America/Los_Angeles", () => {
    renderDialog();
    expect(
      screen.getByRole("combobox", { name: "Duration" }),
    ).toHaveTextContent("45 minutes");
    expect(screen.getByTestId("timezone-selector")).toHaveValue(
      "America/Los_Angeles",
    );
  });

  it("emits the IANA key the shared selector hands back, not its label", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog({ defaultAssigneeId: 10 });
    fireEvent.change(screen.getByTestId("timezone-selector"), {
      target: { value: "America/New_York" },
    });
    fireEvent.change(screen.getByLabelText("Date"), {
      target: { value: "2026-08-05" },
    });
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "14:00" },
    });
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ timezone: "America/New_York" }),
    );
  });

  it("preselects the round's current assignee", () => {
    renderDialog({ defaultAssigneeId: 11 });
    expect(
      screen.getByRole("combobox", { name: "Interviewer" }),
    ).toHaveTextContent("Ivan Interviewer");
  });

  it("falls back to the stage default assignee when the round is unassigned", () => {
    renderDialog({ defaultAssigneeId: 10 });
    expect(
      screen.getByRole("combobox", { name: "Interviewer" }),
    ).toHaveTextContent("Eve Evaluator");
  });

  it("keeps submit disabled until interviewer, date and time are filled", async () => {
    const user = userEvent.setup();
    renderDialog({ defaultAssigneeId: null });
    expect(screen.getByRole("button", { name: "Schedule" })).toBeDisabled();

    await pickInterviewer(user, "Eve Evaluator (eve@example.com)");
    expect(
      screen.getByRole("combobox", { name: "Interviewer" }),
    ).toHaveTextContent("Eve Evaluator");
    expect(screen.getByRole("button", { name: "Schedule" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Date"), {
      target: { value: "2026-08-05" },
    });
    expect(screen.getByRole("button", { name: "Schedule" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "14:00" },
    });
    expect(screen.getByRole("button", { name: "Schedule" })).toBeEnabled();
  });

  it("submits wall-clock fields, not a UTC instant", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog({ defaultAssigneeId: 10 });
    fireEvent.change(screen.getByLabelText("Date"), {
      target: { value: "2026-08-05" },
    });
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "14:00" },
    });
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    expect(onSubmit).toHaveBeenCalledWith({
      assigneeId: 10,
      date: "2026-08-05",
      startTime: "14:00",
      durationMinutes: 45,
      timezone: "America/Los_Angeles",
    });
  });

  it("prefills every field from the existing booking in edit mode", () => {
    renderDialog({ mode: "edit", interview: INTERVIEW, defaultAssigneeId: null });
    expect(screen.getByLabelText("Date")).toHaveValue("2026-08-05");
    expect(screen.getByLabelText("Start time")).toHaveValue("14:00");
    expect(
      screen.getByRole("combobox", { name: "Duration" }),
    ).toHaveTextContent("45 minutes");
    expect(screen.getByTestId("timezone-selector")).toHaveValue(
      "America/Los_Angeles",
    );
    expect(
      screen.getByRole("combobox", { name: "Interviewer" }),
    ).toHaveTextContent("Eve Evaluator");
  });

  it("warns that attendees will be notified in edit mode", () => {
    renderDialog({ mode: "edit", interview: INTERVIEW });
    expect(
      screen.getByText(/attendees will be notified/i),
    ).toBeInTheDocument();
  });

  it("lists the invitees and names the organizer", () => {
    renderDialog({
      mode: "edit",
      interview: INTERVIEW,
      candidateName: "Alice Smith",
    });
    // Exact strings from the info block -- the combobox's own display and
    // the hidden native <select> fallback both also contain "Eve Evaluator"
    // as substrings, so a loose regex match would be ambiguous.
    expect(screen.getByText("Candidate: Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("Interviewer: Eve Evaluator")).toBeInTheDocument();
    expect(screen.getByText("Organizer: Jane Smith")).toBeInTheDocument();
  });

  it("titles itself Schedule interview meeting / Edit interview meeting per mode", () => {
    const { rerender } = render(
      <InterviewMeetingDialog
        open
        onOpenChange={vi.fn()}
        mode="schedule"
        interview={null}
        defaultAssigneeId={null}
        interviewPool={POOL}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText("Schedule interview meeting")).toBeInTheDocument();
    rerender(
      <InterviewMeetingDialog
        open
        onOpenChange={vi.fn()}
        mode="edit"
        interview={INTERVIEW}
        defaultAssigneeId={null}
        interviewPool={POOL}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText("Edit interview meeting")).toBeInTheDocument();
  });
});
