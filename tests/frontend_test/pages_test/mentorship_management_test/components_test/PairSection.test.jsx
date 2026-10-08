import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PairSection from "@/pages/MentorshipManagement/components/PairSection";
import { getMeetingLog, updateMeetingLog } from "@/api/mentorshipApi";
import { pairOf } from "../participantDetail.helper";

vi.mock("@/api/mentorshipApi", () => ({
  getMeetingLog: vi.fn(),
  updateMeetingLog: vi.fn(),
}));

const SUBJECT = { userId: 3104, name: "Alice Chen", role: "mentee" };
const ROUND = { roundId: 7, inProgress: true, requiredMeetings: 5 };

const log = (overrides = {}) => ({
  data: {
    roundVersion: "v2",
    roundInProgress: true,
    meetings: [
      {
        meetingId: "gm-80-1",
        startDatetime: "2026-09-02T17:00:00Z",
        endDatetime: "2026-09-02T18:00:00Z",
        isCompleted: true,
        note: [],
        createDatetime: "2026-09-01T17:00:00Z",
      },
    ],
    ...overrides,
  },
});

const renderSection = (props = {}) =>
  render(
    <MemoryRouter>
      <PairSection
        pair={pairOf()}
        subject={SUBJECT}
        round={ROUND}
        canWrite
        open={false}
        onToggle={vi.fn()}
        onMeetingsSaved={vi.fn()}
        {...props}
      />
    </MemoryRouter>,
  );

describe("PairSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMeetingLog.mockResolvedValue(log());
  });

  it("names the partner with their ID, linked to their page on this pair", () => {
    renderSection();
    const link = screen.getByRole("link", { name: "Bob Smith · ID 22" });
    expect(link).toHaveAttribute(
      "href",
      "/mentorship-management/participants/22?round=7&pair=80",
    );
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Meetings 2/5")).toBeInTheDocument();
  });

  it("shows the first meeting in Pacific time while the round is in progress", () => {
    renderSection();
    expect(screen.getByText("First meeting 2026-09-02")).toBeInTheDocument();
  });

  it("says No meeting yet when none has been booked", () => {
    renderSection({ pair: pairOf({ firstMeetingAt: null }) });
    expect(screen.getByText("No meeting yet")).toBeInTheDocument();
  });

  it("leaves first contact off a round that has ended", () => {
    renderSection({ round: { ...ROUND, inProgress: false } });
    expect(screen.queryByText(/First meeting|No meeting yet/)).not.toBeInTheDocument();
  });

  it("marks an active pair's attendance issues", () => {
    renderSection({
      pair: pairOf({
        attendanceIssues: [
          { startDatetime: "2026-09-02T17:00:00Z", note: ["mentee_absent"] },
        ],
      }),
    });
    expect(
      screen.getByRole("button", { name: /Attendance issues/ }),
    ).toBeInTheDocument();
  });

  it("marks an ended pair and gives it no attendance mark", () => {
    renderSection({
      pair: pairOf({
        partner: { ...pairOf().partner, isActive: false },
        attendanceIssues: [
          { startDatetime: "2026-09-02T17:00:00Z", note: ["mentee_absent"] },
        ],
      }),
    });
    expect(screen.getByText("Ended")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Attendance issues/ }),
    ).not.toBeInTheDocument();
  });

  it("does not load meetings until opened", () => {
    renderSection();
    expect(getMeetingLog).not.toHaveBeenCalled();
  });

  it("when open, loads the pair's meetings and lets a writer edit them", async () => {
    renderSection({ open: true });
    await screen.findByText("2026-09-02 · 10:00 - 11:00");
    expect(getMeetingLog).toHaveBeenCalledWith(80);
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("offers no Edit without write access", async () => {
    renderSection({ open: true, canWrite: false });
    await screen.findByText("2026-09-02 · 10:00 - 11:00");
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("offers no Edit when the meeting log says the round has ended", async () => {
    getMeetingLog.mockResolvedValue(log({ roundInProgress: false }));
    renderSection({ open: true });
    await screen.findByText("2026-09-02 · 10:00 - 11:00");
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("saves a deletion after confirming and tells the page", async () => {
    updateMeetingLog.mockResolvedValue(log({ meetings: [] }));
    const onMeetingsSaved = vi.fn();
    renderSection({ open: true, onMeetingsSaved });
    await screen.findByText("2026-09-02 · 10:00 - 11:00");

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete (1)" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm changes" }),
    );

    await waitFor(() =>
      expect(updateMeetingLog).toHaveBeenCalledWith(80, {
        updates: [],
        deletes: ["gm-80-1"],
      }),
    );
    expect(onMeetingsSaved).toHaveBeenCalled();
  });
});
