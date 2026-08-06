import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { toast } from "sonner";
import MeetingLogDialog from "@/pages/MentorshipManagement/components/MeetingLogDialog";

vi.spyOn(toast, "error").mockImplementation(() => {});

const baseProps = {
  open: true,
  onOpenChange: vi.fn(),
  roundName: "Fall 2024",
  roundVersion: "v2",
  subjectName: "Henry Zhang",
  subjectRole: "mentee",
  partnerName: "Sarah Lee",
  partnerRole: "mentor",
  meetings: [],
  loading: false,
  error: false,
  onSave: vi.fn().mockResolvedValue(),
};

/** A single valid meeting fixture for tests that only need meetings.length > 0. */
function makeMeeting(overrides = {}) {
  return {
    meetingId: "gm-80-1",
    startDatetime: "2024-03-01T23:30:00Z",
    endDatetime: "2024-03-02T00:30:00Z",
    isCompleted: true,
    note: [],
    createDatetime: "2024-03-01T15:30:00Z",
    ...overrides,
  };
}

describe("MeetingLogDialog", () => {
  it("renders the title from row data regardless of fetch state", () => {
    render(<MeetingLogDialog {...baseProps} loading />);
    expect(
      screen.getByText(
        "Meeting Log — Henry Zhang (Mentee) with Sarah Lee (Mentor) · Fall 2024",
      ),
    ).toBeInTheDocument();
  });

  it("shows the loading indicator and no table while loading", () => {
    render(<MeetingLogDialog {...baseProps} loading />);
    expect(screen.getByText("Loading meeting log…")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows the inline error message and no table on error", () => {
    render(<MeetingLogDialog {...baseProps} error />);
    expect(
      screen.getByText(
        "Couldn't load meeting log. Close and reopen to try again.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no meetings", () => {
    render(<MeetingLogDialog {...baseProps} meetings={[]} />);
    expect(screen.getByText("No meetings recorded yet.")).toBeInTheDocument();
  });

  it("renders Time Range and Create Datetime column headers", () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        meetings={[
          {
            meetingId: "gm-80-1",
            startDatetime: "2024-03-01T23:30:00Z",
            endDatetime: "2024-03-02T00:30:00Z",
            isCompleted: true,
            note: [],
            createDatetime: "2024-03-01T15:30:00Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("Time Range")).toBeInTheDocument();
    expect(screen.getByText("Create Datetime")).toBeInTheDocument();
    expect(screen.queryByText("Datetime")).not.toBeInTheDocument();
  });

  it("renders one row per meeting with derived numbering, datetime and status", () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        meetings={[
          {
            meetingId: "gm-80-1",
            startDatetime: "2024-03-01T23:30:00Z",
            endDatetime: "2024-03-02T00:30:00Z",
            isCompleted: true,
            note: [],
            createDatetime: "2024-03-01T15:30:00Z",
          },
          {
            meetingId: "gm-80-2",
            startDatetime: "2024-03-08T23:30:00Z",
            endDatetime: "2024-03-09T00:30:00Z",
            isCompleted: false,
            note: [],
            createDatetime: "2024-03-08T15:30:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("2024-03-01 · 15:30 – 16:30")).toBeInTheDocument();
    expect(screen.getByText("2024-03-08 · 15:30 – 16:30")).toBeInTheDocument();
    expect(screen.getByText("2024-03-01 · 07:30")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Incomplete")).toBeInTheDocument();
  });

  it("shows Scheduled instead of Incomplete for a not-yet-completed meeting whose start time is in the future", () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        meetings={[
          {
            meetingId: "gm-80-future",
            startDatetime: "2099-01-01T23:30:00Z",
            endDatetime: "2099-01-02T00:30:00Z",
            isCompleted: false,
            note: [],
            createDatetime: "2026-07-11T00:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.queryByText("Incomplete")).not.toBeInTheDocument();
  });

  it("shows a plain-text placeholder in the Note column for a past incomplete meeting with no note tags", () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        meetings={[
          {
            meetingId: "gm-80-past-no-note",
            startDatetime: "2024-03-01T23:30:00Z",
            endDatetime: "2024-03-02T00:30:00Z",
            isCompleted: false,
            note: [],
            createDatetime: "2024-03-01T15:30:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("No attendance data")).toBeInTheDocument();
  });

  it("substitutes the mentor/mentee name for role-specific note tags", () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        meetings={[
          {
            meetingId: "gm-80-2",
            startDatetime: "2024-03-01T23:30:00Z",
            endDatetime: "2024-03-02T00:30:00Z",
            isCompleted: false,
            note: ["mentor_absent", "mentee_late"],
            createDatetime: "x",
          },
        ]}
      />,
    );
    // partner is mentor ("Sarah Lee"), subject is mentee ("Henry Zhang")
    expect(
      screen.getByText("Sarah Lee absent; Henry Zhang late arrival"),
    ).toBeInTheDocument();
    // this meeting is also past-incomplete, but note tags take precedence over the placeholder
    expect(screen.queryByText("No attendance data")).not.toBeInTheDocument();
  });

  it("renders the unknown/insufficient-duration tags without substituting a name", () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        meetings={[
          {
            meetingId: "gm-80-3",
            startDatetime: "2024-03-01T23:30:00Z",
            endDatetime: "2024-03-02T00:30:00Z",
            isCompleted: false,
            note: ["unknown_absent", "unknown_late", "insufficient_duration"],
            createDatetime: "x",
          },
        ]}
      />,
    );
    expect(
      screen.getByText(
        "Unknown absence; Unknown late arrival; Insufficient duration",
      ),
    ).toBeInTheDocument();
  });

  it("renders no note badges when a meeting has none", () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        meetings={[
          {
            meetingId: "gm-80-1",
            startDatetime: "2024-03-01T23:30:00Z",
            endDatetime: "2024-03-02T00:30:00Z",
            isCompleted: true,
            note: [],
            createDatetime: "x",
          },
        ]}
      />,
    );
    expect(screen.queryByText(/absent|late|duration/i)).not.toBeInTheDocument();
  });

  it("clicking the top-right close button calls onOpenChange(false)", async () => {
    const onOpenChange = vi.fn();
    render(<MeetingLogDialog {...baseProps} onOpenChange={onOpenChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("renders nothing when closed", () => {
    render(<MeetingLogDialog {...baseProps} open={false} />);
    expect(screen.queryByText(/Meeting Log —/)).not.toBeInTheDocument();
  });

  it("shows the Edit button only for a non-empty v2 round", () => {
    const { rerender } = render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v1"
        meetings={[makeMeeting()]}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();

    rerender(
      <MeetingLogDialog {...baseProps} roundVersion="v2" meetings={[]} />,
    );
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();

    rerender(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting()]}
      />,
    );
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("clicking Edit replaces the Edit button with Cancel/Delete/Update; clicking Cancel restores it", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting()]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete (0)" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Update (0)" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update (0)" })).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^Update/ }),
    ).not.toBeInTheDocument();
  });

  it("in edit mode, shows a Complete Status select and Note checkboxes reflecting the meeting's current values", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[
          makeMeeting({
            meetingId: "gm-1",
            isCompleted: false,
            note: ["mentor_absent"],
          }),
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(
      screen.getByRole("combobox", { name: "Complete Status" }),
    ).toHaveTextContent("Incomplete");
    // partner is mentor ("Sarah Lee") per baseProps
    expect(screen.getByRole("button", { name: "Note" })).toHaveTextContent(
      "Sarah Lee absent",
    );
    await userEvent.click(screen.getByRole("button", { name: "Note" }));
    expect(
      screen.getByRole("checkbox", { name: "Sarah Lee absent" }),
    ).toBeChecked();
  });

  it("changing Complete Status and toggling a Note checkbox updates what's displayed", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1", isCompleted: false })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Completed" }));
    expect(
      screen.getByRole("combobox", { name: "Complete Status" }),
    ).toHaveTextContent("Completed");

    expect(screen.getByRole("button", { name: "Note" })).toHaveTextContent(
      "Select",
    );
    await userEvent.click(screen.getByRole("button", { name: "Note" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Sarah Lee late arrival" }),
    );
    expect(screen.getByRole("button", { name: "Note" })).toHaveTextContent(
      "Sarah Lee late arrival",
    );
  });

  it("changing a field back to its original value disables Update again", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1", isCompleted: false })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Completed" }));
    expect(screen.getByRole("button", { name: "Update (1)" })).toBeEnabled();

    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Incomplete" }));

    expect(screen.getByRole("button", { name: "Update (0)" })).toBeDisabled();
  });

  it("disables incompatible Note checkboxes once one is checked, per the mutual-exclusion rules", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1", isCompleted: false })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Note" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Sarah Lee absent" }),
    );

    expect(
      screen.getByRole("checkbox", { name: "Unknown absence" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Henry Zhang absent" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Unknown late arrival" }),
    ).toBeEnabled();
  });

  it("disables the absent Note checkboxes once Complete Status is Completed", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1", isCompleted: false })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Completed" }));
    await userEvent.click(screen.getByRole("button", { name: "Note" }));

    expect(
      screen.getByRole("checkbox", { name: "Unknown absence" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Sarah Lee absent" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Henry Zhang absent" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Unknown late arrival" }),
    ).toBeEnabled();
  });

  it("disables the Completed option once an absent tag is selected", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[
          makeMeeting({
            meetingId: "gm-1",
            isCompleted: false,
            note: ["mentor_absent"],
          }),
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );

    expect(screen.getByRole("option", { name: "Completed" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("checking a row's checkbox immediately locks its cells to read-only; unchecking it restores them", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[
          makeMeeting({ meetingId: "gm-1" }),
          makeMeeting({ meetingId: "gm-2" }),
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(
      screen.getAllByRole("combobox", { name: "Complete Status" }),
    ).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Delete (0)" })).toBeDisabled();

    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    expect(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).toBeChecked();
    // gm-1 locked to read-only cells; only gm-2 remains editable.
    expect(
      screen.getAllByRole("combobox", { name: "Complete Status" }),
    ).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Delete (1)" })).toBeEnabled();

    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    expect(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).not.toBeChecked();
    expect(
      screen.getAllByRole("combobox", { name: "Complete Status" }),
    ).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Delete (0)" })).toBeDisabled();
  });

  it("checking then unchecking a row for deletion doesn't affect an edit made to it beforehand", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1", isCompleted: true })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Incomplete" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    // The row's edit is hidden while checked, so it shouldn't count toward Update.
    expect(screen.getByRole("button", { name: "Update (0)" })).toBeDisabled();

    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );

    expect(
      screen.getByRole("combobox", { name: "Complete Status" }),
    ).toHaveTextContent("Incomplete");
    expect(screen.getByRole("button", { name: "Update (1)" })).toBeEnabled();
  });

  it("selecting all via the header checkbox checks every row", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[
          makeMeeting({ meetingId: "gm-1" }),
          makeMeeting({ meetingId: "gm-2" }),
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Select all meetings for deletion",
      }),
    );

    expect(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Select meeting 2 for deletion" }),
    ).toBeChecked();
    expect(screen.getByRole("button", { name: "Delete (2)" })).toBeEnabled();

    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Select all meetings for deletion",
      }),
    );
    expect(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Select meeting 2 for deletion" }),
    ).not.toBeChecked();
  });

  it("Cancel discards checked rows and edited fields", async () => {
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1" })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).not.toBeChecked();
  });

  it("clicking Update opens a confirmation for just the pending edits; Confirm changes sends only updates and exits back to the read-only view", async () => {
    const onSave = vi.fn().mockResolvedValue();
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        onSave={onSave}
        meetings={[makeMeeting({ meetingId: "gm-1", isCompleted: false })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Completed" }));
    await userEvent.click(screen.getByRole("button", { name: "Update (1)" }));

    expect(screen.getByText("Save changes?")).toBeInTheDocument();
    expect(screen.getByText("Updates: 1")).toBeInTheDocument();
    expect(screen.queryByText(/^Deletes:/)).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Confirm changes" }),
    );

    expect(onSave).toHaveBeenCalledWith({
      updates: [{ meetingId: "gm-1", isCompleted: true }],
      deletes: [],
    });
    // The dialog itself never closes, but edit mode exits back to read-only.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("combobox", { name: "Complete Status" }),
    ).not.toBeInTheDocument();
  });

  it("clicking Delete opens a confirmation for just the checked rows; Confirm changes sends only deletes and exits back to the read-only view", async () => {
    const onSave = vi.fn().mockResolvedValue();
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        onSave={onSave}
        meetings={[makeMeeting({ meetingId: "gm-1" })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete (1)" }));

    expect(screen.getByText("Delete meetings?")).toBeInTheDocument();
    expect(screen.getByText("Deletes: 1")).toBeInTheDocument();
    expect(screen.queryByText(/^Updates:/)).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Confirm changes" }),
    );

    expect(onSave).toHaveBeenCalledWith({
      updates: [],
      deletes: ["gm-1"],
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).not.toBeInTheDocument();
  });

  it("on save failure, shows an error toast and keeps edit-mode state so the admin can retry", async () => {
    const onSave = vi.fn().mockRejectedValue({ message: "network error" });
    render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        onSave={onSave}
        meetings={[makeMeeting({ meetingId: "gm-1", isCompleted: false })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Complete Status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Completed" }));
    await userEvent.click(screen.getByRole("button", { name: "Update (1)" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm changes" }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("network error"),
    );
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Complete Status" }),
    ).toHaveTextContent("Completed");
  });

  it("closing and reopening the dialog resets edit mode back to the read-only view", async () => {
    const { rerender } = render(
      <MeetingLogDialog
        {...baseProps}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1" })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();

    // The parent never unmounts MeetingLogDialog; it only flips `open`.
    rerender(
      <MeetingLogDialog
        {...baseProps}
        open={false}
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1" })]}
      />,
    );
    rerender(
      <MeetingLogDialog
        {...baseProps}
        open
        roundVersion="v2"
        meetings={[makeMeeting({ meetingId: "gm-1" })]}
      />,
    );

    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^Update/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).not.toBeInTheDocument();
  });
});
