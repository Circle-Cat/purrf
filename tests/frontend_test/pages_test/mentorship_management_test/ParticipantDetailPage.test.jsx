import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ParticipantDetailPage from "@/pages/MentorshipManagement/ParticipantDetailPage";
import {
  addParticipantNote,
  getAllMentorshipRounds,
  getMeetingLog,
  getMentorshipApprovers,
  getParticipantDetail,
  getParticipantEmails,
  refreshParticipantEmails,
  replyParticipantEmail,
  searchParticipants,
  sendParticipantEmail,
} from "@/api/mentorshipApi";
import { getRaisedBlockRequests } from "@/api/adminAccountsApi";
import { toast } from "sonner";
import { conversationOf } from "../../components_test/email_test/email.helper";
import { listPersonSends } from "@/api/mentorshipEmailApi";
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
  requestParticipantMark: vi.fn(),
  requestParticipantWithdrawal: vi.fn(),
  getParticipantEmails: vi.fn(),
  sendParticipantEmail: vi.fn(),
  replyParticipantEmail: vi.fn(),
  refreshParticipantEmails: vi.fn(),
  participantEmailAttachmentUrl: vi.fn(),
}));
vi.mock("@/api/adminAccountsApi", () => ({
  createBlockRequest: vi.fn(),
  getBlockPreflight: vi.fn(),
  getUserAdmins: vi.fn(),
  getRaisedBlockRequests: vi.fn(),
  reassignBlockRequest: vi.fn(),
  withdrawBlockRequest: vi.fn(),
}));
vi.mock("@/api/mentorshipEmailApi", () => ({
  listPersonSends: vi.fn(),
  markNotified: vi.fn(),
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
    getRaisedBlockRequests.mockResolvedValue({ data: [] });

    getParticipantEmails.mockResolvedValue({
      data: conversationOf({ threads: [] }),
    });
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
    listPersonSends.mockResolvedValue([
      {
        sendId: 14,
        stage: "match_result",
        subject: "Your match",
        delivered: true,
        reason: null,
        at: "2026-10-12T16:00:00Z",
      },
    ]);
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

  it("shows the pending block request in the account state chips", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        pendingBlockRequest: {
          requestId: 5,
          reviewer: { userId: 77, name: "Uma Admin" },
        },
      }),
    });
    renderPage();
    const heading = await screen.findByRole("heading", { name: "Alice Chen" });
    expect(
      within(heading.parentElement).getByText("Block requested"),
    ).toBeInTheDocument();
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

  it("says once, for the whole page, that times are Pacific", async () => {
    renderPage();
    await waitFor(() => expect(getMeetingLog).toHaveBeenCalledWith(80));
    expect(
      screen.getAllByText(/^All times .* America\/Los_Angeles\.$/),
    ).toHaveLength(1);
    expect(
      screen.getByText("All times on this page are in America/Los_Angeles."),
    ).toBeInTheDocument();
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

  it("makes a round not in progress read-only", async () => {
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
      await screen.findByText(
        "This round is not in progress. The page is read-only.",
      ),
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

  it("shows the new problem and the exemption control after an earlier exemption", async () => {
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        exempted: true,
        registration: registrationOf({
          approvalStatus: "signed_up",
          pairs: [],
          exemptionFindings: [
            { reason: "red_flag", roundId: 7, roundName: "Fall 2026" },
          ],
        }),
      }),
    });
    renderPage();

    expect(
      await screen.findByText("Exempted earlier this round"),
    ).toBeInTheDocument();
    expect(screen.getByText("Red flag in this round")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request exemption" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Exempted$/)).not.toBeInTheDocument();
  });

  it("does not call a person cleared when a mark came after their exemption", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        exempted: true,
        notes: [
          noteOf({
            noteId: 2,
            tag: "no_show",
            pairId: 80,
            createdAt: "2026-09-05T18:00:00Z",
          }),
          noteOf({
            noteId: 1,
            tag: "matching_exemption",
            createdAt: "2026-09-03T18:00:00Z",
          }),
        ],
      }),
    });
    renderPage();

    expect(
      await screen.findByText("Exempted earlier this round"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Exempted$/)).not.toBeInTheDocument();
  });

  it("keeps the plain Exempted when the only mark came before the exemption", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        exempted: true,
        notes: [
          noteOf({
            noteId: 2,
            tag: "matching_exemption",
            createdAt: "2026-09-05T18:00:00Z",
          }),
          noteOf({
            noteId: 1,
            tag: "no_show",
            pairId: 80,
            createdAt: "2026-09-03T18:00:00Z",
          }),
        ],
      }),
    });
    renderPage();

    expect(await screen.findByText("Exempted")).toBeInTheDocument();
  });

  it("counts this round's marks in the header from the notes", async () => {
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        notes: [
          noteOf({ noteId: 3, tag: "no_show", pairId: 80 }),
          noteOf({ noteId: 2, tag: "no_show", pairId: 80 }),
          noteOf({ noteId: 1, tag: "red_flag" }),
        ],
      }),
    });
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Alice Chen" });
    expect(
      within(heading.parentElement).getByText("No show \u00d72"),
    ).toBeInTheDocument();
    expect(
      within(heading.parentElement).getByText("Red flag"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("with Bob Smith")).toHaveLength(2);
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

  describe("change status / flag", () => {
    const pendingWithdrawal = {
      requestId: 41,
      action: "withdraw_participant",
      raisedBy: { userId: 9, name: "Dana Wu" },
      reviewer: { userId: 8, name: "Rae Kim" },
      reason: null,
      createdAt: "2026-10-09T08:00:00Z",
    };

    beforeEach(() => {
      useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
      getMentorshipApprovers.mockResolvedValue({
        data: [{ userId: 8, name: "Rae Kim" }],
      });
    });

    it("sits beside Block from Purrf and opens on Withdraw from round", async () => {
      const user = userEvent.setup();
      renderPage();

      const button = await screen.findByRole("button", {
        name: "Change status / flag",
      });
      expect(
        screen.getByRole("button", { name: "Block from Purrf" }),
      ).toBeInTheDocument();
      await user.click(button);

      expect(await screen.findByRole("dialog")).toHaveTextContent(
        "Withdraw from round",
      );
    });

    it.each([
      ["once they are withdrawn", { approvalStatus: "withdrawn" }],
      ["for a rejected registration", { approvalStatus: "rejected" }],
    ])("offers only the marks %s", async (_label, overrides) => {
      const user = userEvent.setup();
      getParticipantDetail.mockResolvedValue({
        data: detailOf({ registration: registrationOf(overrides) }),
      });
      renderPage();

      await user.click(
        await screen.findByRole("button", { name: "Change status / flag" }),
      );

      const dialog = await screen.findByRole("dialog");
      expect(
        within(dialog).getByRole("option", { name: "Mark as no show" }),
      ).toBeInTheDocument();
      expect(
        within(dialog).getByRole("option", { name: "Raise a red flag" }),
      ).toBeInTheDocument();
      expect(
        within(dialog).queryByRole("option", { name: "Withdraw from round" }),
      ).not.toBeInTheDocument();
    });

    it("offers no no show to someone who had no pair", async () => {
      const user = userEvent.setup();
      getParticipantDetail.mockResolvedValue({
        data: detailOf({ registration: registrationOf({ pairs: [] }) }),
      });
      renderPage();

      await user.click(
        await screen.findByRole("button", { name: "Change status / flag" }),
      );

      const dialog = await screen.findByRole("dialog");
      expect(
        within(dialog).queryByRole("option", { name: "Mark as no show" }),
      ).not.toBeInTheDocument();
      expect(
        within(dialog).getByRole("option", { name: "Raise a red flag" }),
      ).toBeInTheDocument();
    });

    it("starts over on the first type each time it opens", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(
        await screen.findByRole("button", { name: "Change status / flag" }),
      );
      await user.selectOptions(
        screen.getByLabelText("What are you asking for"),
        "mark_red_flag",
      );
      await user.click(screen.getByRole("button", { name: "Cancel" }));
      await user.click(
        screen.getByRole("button", { name: "Change status / flag" }),
      );

      expect(screen.getByLabelText("What are you asking for")).toHaveValue(
        "withdraw_participant",
      );
    });

    it("is not offered with matching off, to a reader, or after the round", async () => {
      for (const setup of [
        () => useFeatureFlags.mockReturnValue({}),
        () =>
          useAuth.mockReturnValue({
            permissions: [READ],
            user: { userId: 9 },
          }),
        () =>
          getParticipantDetail.mockResolvedValue({
            data: detailOf({
              round: {
                roundId: 7,
                name: "Fall 2026",
                requiredMeetings: 5,
                inProgress: false,
              },
            }),
          }),
      ]) {
        setup();
        const { unmount } = renderPage();
        await screen.findByRole("heading", { name: "Alice Chen" });
        expect(
          screen.queryByRole("button", { name: "Change status / flag" }),
        ).not.toBeInTheDocument();
        unmount();
        useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
        useAuth.mockReturnValue({
          permissions: [READ, WRITE],
          user: { userId: 9 },
        });
        getParticipantDetail.mockResolvedValue({ data: detailOf() });
      }
    });

    it("lists what waits on a decision below the round and stops offering that request", async () => {
      const user = userEvent.setup();
      getParticipantDetail.mockResolvedValue({
        data: detailOf({ pendingRequests: [pendingWithdrawal] }),
      });
      renderPage();

      const block = await screen.findByRole("region", {
        name: "Waiting on a decision",
      });
      expect(
        within(block).getByText(
          "Withdrawal from round \u2014 raised by Dana Wu \u00b7 sent to Rae Kim",
        ),
      ).toBeInTheDocument();
      expect(
        within(block).getByRole("button", { name: "Withdraw" }),
      ).toBeInTheDocument();

      await user.click(
        screen.getByRole("button", { name: "Change status / flag" }),
      );
      const kinds = screen.getByLabelText("What are you asking for");
      expect(
        within(kinds)
          .getAllByRole("option")
          .map((o) => o.textContent),
      ).toEqual(["Mark as no show", "Raise a red flag", "End this pair"]);
    });

    it("names the pair a waiting mark is about", async () => {
      getParticipantDetail.mockResolvedValue({
        data: detailOf({
          pendingRequests: [
            { ...pendingWithdrawal, action: "mark_no_show", pairId: 80 },
          ],
        }),
      });
      renderPage();

      const block = await screen.findByRole("region", {
        name: "Waiting on a decision",
      });
      expect(
        within(block).getByText(
          "No show mark \u2014 raised by Dana Wu \u00b7 sent to Rae Kim \u2014 about the pair with Bob Smith",
        ),
      ).toBeInTheDocument();
    });

    it("has no Waiting on a decision block when nothing waits", async () => {
      renderPage();
      await screen.findByRole("heading", { name: "Alice Chen" });
      expect(
        screen.queryByRole("region", { name: "Waiting on a decision" }),
      ).not.toBeInTheDocument();
    });

    it("keeps notes writable after a withdrawal", async () => {
      getParticipantDetail.mockResolvedValue({
        data: detailOf({
          registration: registrationOf({ approvalStatus: "withdrawn" }),
        }),
      });
      renderPage();
      expect(
        await screen.findByRole("button", { name: "Add a note" }),
      ).toBeInTheDocument();
    });
  });

  it("shows the person's Kit notifications in the timeline when Kit email is on", async () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.MENTORSHIP_KIT_EMAIL]: true,
    });
    renderPage();
    expect(
      await screen.findByText("Match result · Your match"),
    ).toBeInTheDocument();
    expect(listPersonSends).toHaveBeenCalledWith("7", "3104");
  });

  it("asks nothing about Kit notifications when Kit email is off", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Alice Chen" });
    expect(listPersonSends).not.toHaveBeenCalled();
    expect(screen.queryByText("Notification")).not.toBeInTheDocument();
  });

  it("offers Mark as notified with the Kit flag, knowing what Kit sent and what was marked", async () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.MENTORSHIP_KIT_EMAIL]: true,
    });
    getParticipantDetail.mockResolvedValue({
      data: detailOf({
        notes: [
          noteOf({
            noteId: 77,
            tag: "notified",
            notificationStage: "onboarding_reminder",
          }),
        ],
      }),
    });
    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Mark as notified" }),
    );
    const dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).getByText("Mark as notified — Alice Chen"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("option", {
        name: "Match result (already notified)",
      }),
    ).toBeDisabled();
    expect(
      within(dialog).getByRole("option", {
        name: "Onboarding reminder (already notified)",
      }),
    ).toBeDisabled();
    expect(
      within(dialog).getByRole("option", { name: "Mid-term reminder" }),
    ).toBeEnabled();
    expect(
      within(dialog).queryByRole("option", { name: /New round invitation/ }),
    ).not.toBeInTheDocument();
  });

  it("does not call a stage notified when Kit's send to them did not go out", async () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.MENTORSHIP_KIT_EMAIL]: true,
    });
    listPersonSends.mockResolvedValue([
      {
        sendId: 15,
        stage: "admission",
        subject: "Welcome",
        delivered: false,
        reason: "bounced",
        at: "2026-10-12T16:00:00Z",
      },
    ]);
    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Mark as notified" }),
    );
    const dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("option", { name: "Admission & onboarding" }),
    ).toBeEnabled();
    expect(
      within(dialog).queryByRole("option", {
        name: "Admission & onboarding (already notified)",
      }),
    ).not.toBeInTheDocument();
  });

  it("offers someone not registered only what reaches them", async () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.MENTORSHIP_KIT_EMAIL]: true,
    });
    getParticipantDetail.mockResolvedValue({
      data: detailOf({ registration: null }),
    });
    listPersonSends.mockResolvedValue([]);
    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Mark as notified" }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      "Select a notification…",
      "New round invitation",
      "Admission & onboarding",
      "Onboarding reminder",
    ]);
  });

  it("does not offer Mark as notified without the Kit flag", async () => {
    renderPage();
    await screen.findByRole("button", { name: "Add a note" });
    expect(
      screen.queryByRole("button", { name: "Mark as notified" }),
    ).not.toBeInTheDocument();
  });

  describe("email", () => {
    it("offers Send email beside Block from Purrf and sends to the ticked addresses", async () => {
      const user = userEvent.setup();
      sendParticipantEmail.mockResolvedValue({ data: conversationOf() });
      renderPage();

      const button = await screen.findByRole("button", { name: "Send email" });
      expect(
        within(button.parentElement).getByRole("button", {
          name: "Block from Purrf",
        }),
      ).toBeInTheDocument();
      expect(getParticipantEmails).toHaveBeenCalledWith("7", "3104");
      await user.click(button);

      const dialog = await screen.findByRole("dialog", { name: "Send email" });
      expect(
        within(dialog).getByText("From: mentorship@circlecat.org"),
      ).toBeInTheDocument();
      expect(
        within(dialog).getByRole("checkbox", { name: /alice@x\.com/ }),
      ).toBeChecked();
      expect(
        within(dialog).getByRole("checkbox", { name: /alice\.alt@y\.org/ }),
      ).not.toBeChecked();
      expect(
        within(dialog).queryByRole("combobox", { name: /template/i }),
      ).not.toBeInTheDocument();
      await user.type(within(dialog).getByLabelText("Subject"), "Checking in");
      await user.type(
        within(dialog).getByRole("textbox", { name: "Message" }),
        "How is it going?",
      );
      await user.click(within(dialog).getByRole("button", { name: "Send" }));

      await waitFor(() =>
        expect(sendParticipantEmail).toHaveBeenCalledWith("7", "3104", {
          to: ["alice@x.com"],
          subject: "Checking in",
          body: "How is it going?",
        }),
      );
      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );
      expect(screen.getByText("All good, thanks")).toBeInTheDocument();
      expect(toast.success).toHaveBeenCalledWith("Email sent.");
    });

    it("can send after the round has ended", async () => {
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
        await screen.findByRole("button", { name: "Send email" }),
      ).toBeEnabled();
    });

    it("offers no Send email when this environment cannot send", async () => {
      getParticipantEmails.mockResolvedValue({
        data: conversationOf({ canSend: false, senderAddress: null }),
      });
      renderPage();
      expect(await screen.findByText("All good, thanks")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Send email" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /^Reply/ }),
      ).not.toBeInTheDocument();
    });

    it("lets a reader see the threads but not send, reply or refresh", async () => {
      useAuth.mockReturnValue({ permissions: [READ], user: { userId: 9 } });
      getParticipantEmails.mockResolvedValue({ data: conversationOf() });
      renderPage();
      expect(await screen.findByText("All good, thanks")).toBeInTheDocument();
      for (const name of ["Send email", /^Reply/, "Refresh emails"]) {
        expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
      }
    });

    it("replies to the thread's own address with the newest message seen", async () => {
      const user = userEvent.setup();
      // The thread's replyTo differs from the conversation's defaultTo, so a
      // dialog showing defaultTo would fail this test.
      getParticipantEmails.mockResolvedValue({
        data: conversationOf({
          threads: [
            { ...conversationOf().threads[0], replyTo: "alice.alt@y.org" },
          ],
        }),
      });
      replyParticipantEmail.mockResolvedValue({ data: conversationOf() });
      renderPage();

      await user.click(
        await screen.findByRole("button", { name: "Reply to Checking in" }),
      );
      const dialog = await screen.findByRole("dialog", { name: "Reply" });
      expect(within(dialog).getByText("alice.alt@y.org")).toBeInTheDocument();
      expect(within(dialog).queryByText("alice@x.com")).not.toBeInTheDocument();
      expect(within(dialog).getByLabelText("Subject")).toHaveValue(
        "Re: Checking in",
      );
      await user.type(
        within(dialog).getByRole("textbox", { name: "Message" }),
        "Thanks",
      );
      await user.click(within(dialog).getByRole("button", { name: "Send" }));

      await waitFor(() =>
        expect(replyParticipantEmail).toHaveBeenCalledWith("7", "3104", 41, {
          body: "Thanks",
          lastSeenMessageId: 411,
        }),
      );
    });

    it("closes the compose dialog on moving to another person", async () => {
      const user = userEvent.setup();
      renderPage();
      await user.click(
        await screen.findByRole("button", { name: "Send email" }),
      );
      expect(
        await screen.findByRole("dialog", { name: "Send email" }),
      ).toBeInTheDocument();

      // The open dialog hides the page from role queries and user.click.
      fireEvent.click(screen.getByText("Bob Smith · ID 22").closest("a"));
      await waitFor(() =>
        expect(getParticipantEmails).toHaveBeenCalledWith("7", "22"),
      );
      await waitFor(() =>
        expect(screen.getByTestId("where")).toHaveTextContent(
          "/mentorship-management/participants/22",
        ),
      );
      await screen.findByText("Bob Smith · ID 22");

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("refreshes the emails and says how many messages came in", async () => {
      const user = userEvent.setup();
      refreshParticipantEmails.mockResolvedValue({
        data: { conversation: conversationOf(), newReplies: 1 },
      });
      renderPage();

      await user.click(
        await screen.findByRole("button", { name: "Refresh emails" }),
      );
      expect(await screen.findByText("1 new message")).toBeInTheDocument();
      expect(refreshParticipantEmails).toHaveBeenCalledWith("7", "3104");
      expect(screen.getByText("All good, thanks")).toBeInTheDocument();
    });

    it("warns that a blocked person is still emailed", async () => {
      const user = userEvent.setup();
      getParticipantDetail.mockResolvedValue({
        data: detailOf({
          person: { ...detailOf().person, isBlocked: true },
        }),
      });
      renderPage();
      await user.click(
        await screen.findByRole("button", { name: "Send email" }),
      );
      const dialog = await screen.findByRole("dialog", { name: "Send email" });
      expect(
        within(dialog).getByText(
          "Alice Chen is blocked from Purrf. The email is still sent.",
        ),
      ).toBeInTheDocument();
    });

    it("keeps Send email disabled when the person has no address", async () => {
      getParticipantEmails.mockResolvedValue({
        data: conversationOf({
          threads: [],
          defaultTo: null,
          recipientOptions: [],
        }),
      });
      renderPage();
      const button = await screen.findByRole("button", { name: "Send email" });
      expect(button).toBeDisabled();
      expect(button).toHaveAttribute("title", "No email address on file");
    });
  });
});
