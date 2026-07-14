import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import MeetingLogDialog from "@/pages/MentorshipManagement/components/MeetingLogDialog";

const baseProps = {
  open: true,
  onOpenChange: vi.fn(),
  roundName: "Fall 2024",
  subjectName: "Henry Zhang",
  subjectRole: "mentee",
  partnerName: "Sarah Lee",
  partnerRole: "mentor",
  meetings: [],
  loading: false,
  error: false,
};

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
});
