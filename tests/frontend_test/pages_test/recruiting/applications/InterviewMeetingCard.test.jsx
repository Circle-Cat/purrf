import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InterviewMeetingCard from "@/pages/Recruiting/applications/InterviewMeetingCard";

const VIEWER_TZ = "America/Los_Angeles";

const INTERVIEW = {
  interviewId: 7,
  stage: "behavioral",
  round: 1,
  startAt: "2026-08-05T21:00:00Z",
  endAt: "2026-08-05T21:45:00Z",
  meetLink: "https://meet.google.com/abc-defg-hij",
  assigneeId: 10,
  assigneeName: "Eve Evaluator",
  scheduledByName: "Jane Smith",
};

describe("InterviewMeetingCard", () => {
  it("offers scheduling when nothing is booked", () => {
    render(
      <InterviewMeetingCard interview={null} round={1} timezone={VIEWER_TZ} />,
    );
    expect(screen.getByText("Interview Meeting")).toBeInTheDocument();
    expect(screen.getByText("Not scheduled")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Schedule meeting" }),
    ).toBeEnabled();
  });

  it("keeps the schedule button enabled with no interviewer assigned", () => {
    // The interviewer is picked inside the dialog, so an unassigned round
    // must not block the entry point.
    render(
      <InterviewMeetingCard
        interview={null}
        round={1}
        timezone={VIEWER_TZ}
        assigneeId={null}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Schedule meeting" }),
    ).toBeEnabled();
  });

  it("renders the booked time in the viewer's zone, naming the zone in IANA form", () => {
    render(
      <InterviewMeetingCard
        interview={INTERVIEW}
        round={1}
        timezone={VIEWER_TZ}
      />,
    );
    // 21:00Z on 2026-08-05 is 14:00 in America/Los_Angeles.
    expect(screen.getByText(/2026-08-05/)).toBeInTheDocument();
    expect(screen.getByText(/14:00 - 14:45/)).toBeInTheDocument();
    expect(screen.getByText(/America\/Los_Angeles/)).toBeInTheDocument();
    // No derived abbreviation: the IANA name is unambiguous on its own.
    expect(screen.queryByText(/PDT|PST/)).toBeNull();
  });

  it("follows the viewer's zone, not the one it was booked in", () => {
    // Same instant, a reader in Taipei: 21:00Z is 05:00 the NEXT day there.
    // Mutation check -- hardcode a zone in the card and this goes red.
    render(
      <InterviewMeetingCard
        interview={INTERVIEW}
        round={1}
        timezone="Asia/Taipei"
      />,
    );
    expect(screen.getByText(/2026-08-06/)).toBeInTheDocument();
    expect(screen.getByText(/05:00 - 05:45/)).toBeInTheDocument();
    expect(screen.getByText(/Asia\/Taipei/)).toBeInTheDocument();
  });

  it("shows the meet link and both actions once booked", () => {
    render(
      <InterviewMeetingCard
        interview={INTERVIEW}
        round={1}
        timezone={VIEWER_TZ}
      />,
    );
    expect(
      screen.getByText("meet.google.com/abc-defg-hij"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("marks a meeting whose time has passed as Past", () => {
    render(
      <InterviewMeetingCard
        interview={{
          ...INTERVIEW,
          startAt: "2020-01-01T00:00:00Z",
          endAt: "2020-01-01T00:45:00Z",
        }}
        round={1}
        timezone={VIEWER_TZ}
      />,
    );
    expect(screen.getByText("Past")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeEnabled();
  });

  it("labels the round when past the first", () => {
    render(
      <InterviewMeetingCard
        interview={{ ...INTERVIEW, round: 2 }}
        round={2}
        timezone={VIEWER_TZ}
      />,
    );
    expect(screen.getByText("Session 2")).toBeInTheDocument();
  });

  it("warns and drops Edit when the application is terminal", () => {
    render(
      <InterviewMeetingCard
        interview={INTERVIEW}
        round={1}
        timezone={VIEWER_TZ}
        isTerminal
      />,
    );
    expect(screen.getByText(/still on the calendar/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("calls back on each action", async () => {
    const onSchedule = vi.fn();
    const onEdit = vi.fn();
    const onCancel = vi.fn();
    const { rerender } = render(
      <InterviewMeetingCard
        interview={null}
        round={1}
        timezone={VIEWER_TZ}
        onSchedule={onSchedule}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Schedule meeting" }),
    );
    expect(onSchedule).toHaveBeenCalledTimes(1);

    rerender(
      <InterviewMeetingCard
        interview={INTERVIEW}
        round={1}
        timezone={VIEWER_TZ}
        onEdit={onEdit}
        onCancel={onCancel}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows a read.all viewer the booked state with no controls", () => {
    render(
      <InterviewMeetingCard
        interview={INTERVIEW}
        round={1}
        timezone={VIEWER_TZ}
        isOwner={false}
      />,
    );
    // Same state a read.all viewer is entitled to see...
    expect(screen.getByText(/2026-08-05/)).toBeInTheDocument();
    expect(screen.getByText(/14:00 - 14:45/)).toBeInTheDocument();
    expect(screen.getByText(/America\/Los_Angeles/)).toBeInTheDocument();
    expect(
      screen.getByText("meet.google.com/abc-defg-hij"),
    ).toBeInTheDocument();
    // ...none of the owner's controls.
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("shows a read.all viewer the not-scheduled state with no Schedule button", () => {
    render(
      <InterviewMeetingCard
        interview={null}
        round={1}
        timezone={VIEWER_TZ}
        isOwner={false}
      />,
    );
    expect(screen.getByText("Not scheduled")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Schedule meeting" }),
    ).toBeNull();
  });
});
