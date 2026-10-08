import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ParticipationHistory from "@/pages/MentorshipManagement/components/ParticipationHistory";
import { getParticipantDetail, getMeetingLog } from "@/api/mentorshipApi";
import {
  detailOf,
  noteOf,
  pairOf,
  registrationOf,
} from "../participantDetail.helper";

vi.mock("@/api/mentorshipApi", () => ({
  getParticipantDetail: vi.fn(),
  getMeetingLog: vi.fn(),
  updateMeetingLog: vi.fn(),
  addParticipantNote: vi.fn(),
}));

const SPRING = {
  ...registrationOf({
    roundId: 3,
    roundName: "Spring 2026",
    approvalStatus: "matched",
    pairs: [pairOf({ pairId: 61, completedMeetingCount: 4 })],
  }),
  exempted: true,
};

const renderHistory = (history = [SPRING]) =>
  render(
    <MemoryRouter>
      <ParticipationHistory
        userId={3104}
        subjectName="Alice Chen"
        history={history}
      />
    </MemoryRouter>,
  );

describe("ParticipationHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMeetingLog.mockResolvedValue({
      data: { roundVersion: "v2", roundInProgress: true, meetings: [] },
    });
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        round: {
          roundId: 3,
          name: "Spring 2026",
          requiredMeetings: 5,
          inProgress: false,
        },
        registration: SPRING,
        notes: [noteOf({ body: "Spring note" })],
      }),
    });
  });

  it("says so when there is no earlier round", () => {
    renderHistory([]);
    expect(screen.getByText("No earlier rounds.")).toBeInTheDocument();
  });

  it("summarises each round on one row", () => {
    renderHistory();
    const row = screen.getByRole("button", { name: /Spring 2026/ });
    expect(within(row).getByText("Mentee")).toBeInTheDocument();
    expect(row).toHaveTextContent("matched");
    expect(row).toHaveTextContent("Bob Smith · 4/5");
    expect(within(row).getByText("Exempted")).toBeInTheDocument();
  });

  it("loads nothing until a row is opened, then that round, read-only", async () => {
    renderHistory();
    expect(getParticipantDetail).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /Spring 2026/ }));

    expect(await screen.findByText("Spring note")).toBeInTheDocument();
    expect(getParticipantDetail).toHaveBeenCalledWith(3, 3104);
    expect(
      screen.queryByRole("button", { name: "Add a note" }),
    ).not.toBeInTheDocument();
  });
});
