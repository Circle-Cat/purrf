import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ParticipantDetailPage from "@/pages/MentorshipManagement/ParticipantDetailPage";
import {
  addParticipantNote,
  getAllMentorshipRounds,
  getMeetingLog,
  getParticipantDetail,
  searchParticipants,
} from "@/api/mentorshipApi";
import { useAuth } from "@/context/auth";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import {
  detailOf,
  noteOf,
  pairOf,
  registrationOf,
} from "./participantDetail.helper";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
  searchParticipants: vi.fn(),
  getParticipantDetail: vi.fn(),
  getMeetingLog: vi.fn(),
  updateMeetingLog: vi.fn(),
  addParticipantNote: vi.fn(),
  getMentorshipApprovers: vi.fn(),
  requestMatchingExemption: vi.fn(),
  decideMentorshipApproval: vi.fn(),
  reassignMentorshipApproval: vi.fn(),
  withdrawMentorshipApproval: vi.fn(),
}));
vi.mock("@/api/adminAccountsApi", () => ({
  createBlockRequest: vi.fn(),
  getBlockPreflight: vi.fn(),
  getUserAdmins: vi.fn(),
}));
vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

const READ = "mentorship.admin.read";
const WRITE = "mentorship.admin.write";

const Probe = () => {
  const location = useLocation();
  return <div data-testid="where">{location.pathname + location.search}</div>;
};

const renderPage = (
  entry = "/mentorship-management/participants/3104?round=7",
  state,
) =>
  render(
    <MemoryRouter
      initialEntries={[
        {
          pathname: entry.split("?")[0],
          search: entry.includes("?") ? `?${entry.split("?")[1]}` : "",
          state,
        },
      ]}
    >
      <Routes>
        <Route
          path="/mentorship-management/participants/:userId"
          element={<ParticipantDetailPage />}
        />
        <Route path="/mentorship-management" element={<div>Management</div>} />
      </Routes>
      <Probe />
    </MemoryRouter>,
  );

describe("ParticipantDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      permissions: [READ, WRITE],
      user: { userId: 9 },
    });
    useFeatureFlags.mockReturnValue({});
    getParticipantDetail.mockResolvedValue({ data: detailOf() });
    getMeetingLog.mockResolvedValue({
      data: { roundVersion: "v2", roundInProgress: true, meetings: [] },
    });
  });

  it("names the person with ID, role, internal and email, and their account state", async () => {
    renderPage();
    const heading = await screen.findByRole("heading", { name: "Alice Chen" });
    expect(
      screen.getByText("ID 3104 · Mentee · Internal · alice@x.com"),
    ).toBeInTheDocument();
    // The pair's own badge also says Active, so look inside the header.
    expect(
      within(heading.parentElement).getByText("Active"),
    ).toBeInTheDocument();
    expect(getParticipantDetail).toHaveBeenCalledWith("7", "3104");
  });

  it("shows this round's status, training and pair", async () => {
    renderPage();
    const block = await screen.findByRole("region", { name: "Fall 2026" });
    expect(within(block).getByText("matched")).toBeInTheDocument();
    expect(within(block).getByText("Training done")).toBeInTheDocument();
    expect(
      within(block).getByRole("link", { name: "Bob Smith · ID 22" }),
    ).toBeInTheDocument();
  });

  it("opens the only pair without being asked", async () => {
    renderPage();
    await waitFor(() => expect(getMeetingLog).toHaveBeenCalledWith(80));
  });

  it("opens the pair named in the URL, not the others", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        registration: registrationOf({
          participantRole: "mentor",
          pairs: [
            pairOf({ pairId: 80 }),
            pairOf({
              pairId: 81,
              partner: { ...pairOf().partner, id: 23, firstName: "Cy" },
            }),
          ],
        }),
      }),
    });
    renderPage("/mentorship-management/participants/3104?round=7&pair=81");
    await waitFor(() => expect(getMeetingLog).toHaveBeenCalledWith(81));
    expect(getMeetingLog).not.toHaveBeenCalledWith(80);
  });

  it("keeps a closed pair closed and does not scroll again after a refetch", async () => {
    const scroll = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    try {
      renderPage("/mentorship-management/participants/3104?round=7&pair=80");
      await waitFor(() => expect(getMeetingLog).toHaveBeenCalledWith(80));
      expect(scroll).toHaveBeenCalledTimes(1);

      await userEvent.click(
        screen.getByRole("button", { name: /Hide meetings with Bob Smith/ }),
      );
      addParticipantNote.mockResolvedValue({ data: noteOf() });
      getParticipantDetail.mockResolvedValue({
        data: detailOf({ notes: [noteOf()] }),
      });
      await userEvent.click(screen.getByRole("button", { name: "Add a note" }));
      await userEvent.type(screen.getByLabelText("Note"), "Called her");
      await userEvent.click(screen.getByRole("button", { name: "Save note" }));
      expect(
        await screen.findByText("Asked to move the first meeting."),
      ).toBeInTheDocument();

      expect(
        screen.getByRole("button", { name: /Show meetings with Bob Smith/ }),
      ).toHaveAttribute("aria-expanded", "false");
      expect(getMeetingLog).toHaveBeenCalledTimes(1);
      expect(scroll).toHaveBeenCalledTimes(1);
    } finally {
      scroll.mockRestore();
    }
  });

  it("says when the person did not register for the round", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({ registration: null }),
    });
    renderPage();
    expect(
      await screen.findByText("Not registered for this round."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("ID 3104 · Not registered · Internal · alice@x.com"),
    ).toBeInTheDocument();
  });

  it("says No pair this round for someone registered without a pair", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        registration: registrationOf({
          pairs: [],
          approvalStatus: "signed_up",
        }),
      }),
    });
    renderPage();
    expect(await screen.findByText("No pair this round")).toBeInTheDocument();
  });

  it("makes an ended round read-only", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        round: {
          roundId: 7,
          name: "Fall 2026",
          requiredMeetings: 5,
          inProgress: false,
        },
      }),
    });
    renderPage();
    expect(
      await screen.findByText("This round has ended. The page is read-only."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add a note" }),
    ).not.toBeInTheDocument();
  });

  it("gives a reader no way to write", async () => {
    useAuth.mockReturnValue({ permissions: [READ], user: { userId: 9 } });
    renderPage();
    await screen.findByRole("heading", { name: "Alice Chen" });
    expect(
      screen.queryByRole("button", { name: "Add a note" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Block from Purrf" }),
    ).not.toBeInTheDocument();
  });

  it("lists the history problems and, with matching on, the exemption control", async () => {
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        registration: registrationOf({
          approvalStatus: "signed_up",
          pairs: [],
          exemptionFindings: [
            {
              reason: "meetings_short",
              roundId: 3,
              roundName: "Spring 2026",
              completed: 1,
              required: 5,
            },
          ],
        }),
      }),
    });
    renderPage();
    expect(
      await screen.findByText("Meetings short in Spring 2026: 1 of 5"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request exemption" }),
    ).toBeInTheDocument();
  });

  it("shows Exempted once the exemption is granted", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({ exempted: true }),
    });
    renderPage();
    expect(await screen.findByText("Exempted")).toBeInTheDocument();
  });

  it("shows notes and the earlier rounds", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        notes: [noteOf()],
        history: [
          {
            ...registrationOf({ roundId: 3, roundName: "Spring 2026" }),
            exempted: false,
          },
        ],
      }),
    });
    renderPage();
    expect(
      await screen.findByText("Asked to move the first meeting."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Spring 2026/ }),
    ).toBeInTheDocument();
  });

  it("goes back to the list with the filters it came from", async () => {
    renderPage("/mentorship-management/participants/3104?round=7", {
      returnSearch: "?round=7&q=alice",
    });
    await userEvent.click(
      await screen.findByRole("link", { name: "Participants" }),
    );
    expect(screen.getByTestId("where")).toHaveTextContent(
      "/mentorship-management?round=7&q=alice",
    );
  });

  it("without a round, picks the latest round the person registered for", async () => {
    getAllMentorshipRounds.mockResolvedValue({
      data: [
        { id: 9, name: "Spring 2027" },
        { id: 7, name: "Fall 2026" },
        { id: 3, name: "Spring 2026" },
      ],
    });
    searchParticipants.mockResolvedValue({
      data: {
        participantRows: [
          registrationOf({ roundId: 3 }),
          registrationOf({ roundId: 7 }),
        ],
        total: 2,
      },
    });
    renderPage("/mentorship-management/participants/3104");

    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent(
        "/mentorship-management/participants/3104?round=7",
      ),
    );
    expect(searchParticipants).toHaveBeenCalledWith({ userId: 3104 });
  });

  it("without a round and no registration, picks the latest round", async () => {
    getAllMentorshipRounds.mockResolvedValue({
      data: [
        { id: 9, name: "Spring 2027" },
        { id: 7, name: "Fall 2026" },
      ],
    });
    searchParticipants.mockResolvedValue({
      data: { participantRows: [], total: 0 },
    });
    renderPage("/mentorship-management/participants/3104");

    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent("?round=9"),
    );
  });

  it("says it could not load the person", async () => {
    getParticipantDetail.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(
      await screen.findByText("Could not load this participant."),
    ).toBeInTheDocument();
  });
});
