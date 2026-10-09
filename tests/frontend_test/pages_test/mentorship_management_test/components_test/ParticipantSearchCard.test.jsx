import { render, screen, waitFor, within, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import ParticipantSearchCard from "@/pages/MentorshipManagement/components/ParticipantSearchCard";
import AllRoundsTable from "@/pages/MentorshipManagement/components/AllRoundsTable";
import RoundFeedbackPage from "@/pages/MentorshipManagement/RoundFeedbackPage";
import {
  searchParticipants,
  searchUnregistered,
  getMeetingLog,
  updateMeetingLog,
  getRoundFeedback,
  getAllMentorshipRounds,
  getMatchingRun,
  startMatchingRun,
  requestMatchingExemption,
  getMentorshipApprovers,
  decideMentorshipApproval,
} from "@/api/mentorshipApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useAuth } from "@/context/auth";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import {
  listNotifiedStages,
  listKitDrafts,
  createEmailSend,
  refreshEmailPreview,
  confirmEmailSend,
  cancelEmailSend,
} from "@/api/mentorshipEmailApi";
import { toast } from "sonner";

vi.mock("@/api/mentorshipApi", () => ({
  searchParticipants: vi.fn(),
  searchUnregistered: vi.fn(),
  getMeetingLog: vi.fn(),
  updateMeetingLog: vi.fn(),
  getRoundFeedback: vi.fn(),
  getAllMentorshipRounds: vi.fn(),
  getMatchingRun: vi.fn(),
  startMatchingRun: vi.fn(),
  requestMatchingExemption: vi.fn(),
  getMentorshipApprovers: vi.fn(),
  decideMentorshipApproval: vi.fn(),
  reassignMentorshipApproval: vi.fn(),
  withdrawMentorshipApproval: vi.fn(),
}));

vi.mock("@/api/mentorshipEmailApi", () => ({
  listNotifiedStages: vi.fn(),
  listKitDrafts: vi.fn(),
  createEmailSend: vi.fn(),
  refreshEmailPreview: vi.fn(),
  confirmEmailSend: vi.fn(),
  cancelEmailSend: vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));

// Latest first, as the API returns them; the latest has the higher id here so
// that picking the lowest id instead of the first would show.
const TEST_ROUNDS = [
  { id: 7, name: "Fall 2026", isInProgress: true },
  { id: 3, name: "Spring 2026", isInProgress: false },
];

let navigateTo;

const LocationProbe = () => {
  const location = useLocation();
  navigateTo = useNavigate();
  return (
    <>
      <div data-testid="location-path">{location.pathname}</div>
      <div data-testid="location-search">{location.search}</div>
    </>
  );
};

const StateProbe = () => {
  const location = useLocation();
  return <div data-testid="return-search">{location.state?.returnSearch}</div>;
};

const roundsLoaded = () =>
  waitFor(() => expect(screen.getByLabelText("Round")).toBeEnabled());

/**
 * Renders the card at `url` with the API listing `rounds`, and waits for them
 * to load. `rounds: null` leaves the rounds request pending.
 */
const renderCard = async ({ url = "/", rounds = TEST_ROUNDS } = {}) => {
  getAllMentorshipRounds.mockReturnValue(
    rounds === null ? new Promise(() => {}) : Promise.resolve({ data: rounds }),
  );
  const view = render(
    <MemoryRouter initialEntries={[url]}>
      <ParticipantSearchCard />
      <LocationProbe />
    </MemoryRouter>,
  );
  if (rounds?.length) await roundsLoaded();
  else await act(async () => {});
  return view;
};

const urlParams = () =>
  new URLSearchParams(screen.getByTestId("location-search").textContent);

const SEARCHED_PARTICIPANTS = "/?round=7";

const search = () =>
  userEvent.click(screen.getByRole("button", { name: "Search" }));

const mounted = () =>
  waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));

const participantRow = (overrides = {}) => ({
  userId: 11,
  firstName: "Alice",
  lastName: "Doe",
  preferredName: "Alice Doe",
  primaryEmail: "alice@x.com",
  alternativeEmails: [],
  isBlocked: false,
  isDeactivated: false,
  isInternal: false,
  roundName: "Spring 2026",
  participantRole: "mentor",
  approvalStatus: "matched",
  mentorOnboardingStatus: "done",
  menteeOnboardingStatus: "to_do",
  pairs: [pairOf()],
  requiredMeetings: 5,
  ...overrides,
});

const pairOf = ({
  pairId = 80,
  id = 22,
  name = "Bob Smith",
  isActive = true,
  completedMeetingCount = 2,
  attendanceIssues = [],
} = {}) => ({
  pairId,
  partner: {
    id,
    firstName: name.split(" ")[0],
    lastName: name.split(" ")[1],
    preferredName: name,
    isActive,
  },
  completedMeetingCount,
  attendanceIssues,
});

/**
 * The cell in the same row as `node`, under the column headed `header`.
 */
const cellOf = (node, header) => {
  const headers = within(node.closest("table")).getAllByRole("columnheader");
  const index = headers.findIndex((th) => th.textContent === header);
  return node.closest("tr").querySelectorAll("td")[index];
};

const resultsOf = (rows) => ({
  data: { participantRows: rows, total: rows.length },
});

const meetingLogResponse = (roundVersion, meetingId) => ({
  data: {
    roundVersion,
    roundInProgress: true,
    meetings: [
      {
        meetingId,
        startDatetime: "2024-03-01T23:30:00Z",
        endDatetime: "2024-03-02T00:30:00Z",
        isCompleted: true,
        note: [],
        createDatetime: "2024-03-01T15:30:00Z",
      },
    ],
  },
});

describe("ParticipantSearchCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParticipants.mockResolvedValue(resultsOf([]));
    getAllMentorshipRounds.mockResolvedValue({ data: TEST_ROUNDS });
    getMeetingLog.mockResolvedValue({
      data: { roundVersion: "v2", meetings: [] },
    });
    getMatchingRun.mockResolvedValue({ data: { status: "never_run" } });
    startMatchingRun.mockResolvedValue({ data: { runId: 12 } });
    useFeatureFlags.mockReturnValue({});
    useAuth.mockReturnValue({
      permissions: ["mentorship.admin.read", "mentorship.admin.write"],
      user: { userId: 9 },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("when the search runs", () => {
    it("sends no request and shows a hint when the URL has no search", async () => {
      await renderCard();
      await act(async () => {});

      expect(searchParticipants).not.toHaveBeenCalled();
      expect(
        screen.getByText("Set filters and click Search to see participants."),
      ).toBeInTheDocument();
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    });

    it("clicking Search with no filters lists the first page of the latest round", async () => {
      await renderCard();
      await search();

      await mounted();
      const args = searchParticipants.mock.calls[0][0];
      expect(args).toMatchObject({
        roundId: "7",
        limit: 20,
        offset: 0,
        order: "asc",
      });
      [
        "userId",
        "q",
        "accountStatus",
        "internal",
        "onboardingStatus",
        "participantRole",
        "approvalStatus",
        "sortBy",
      ].forEach((key) => expect(args[key]).toBeUndefined());
      expect(screen.getByTestId("location-search").textContent).toBe(
        "?round=7",
      );
    });

    it("runs the search in the URL on open and fills the inputs from it", async () => {
      await renderCard({
        url:
          "/?id=7&q=ali&account=blocked&internal=external" +
          "&training=completed&round=3&role=mentor&approval=matched" +
          "&sort=user_id&order=desc&offset=20",
      });
      await mounted();

      expect(searchParticipants).toHaveBeenCalledWith({
        userId: "7",
        q: "ali",
        accountStatus: "blocked",
        internal: "external",
        onboardingStatus: "completed",
        roundId: "3",
        participantRole: "mentor",
        approvalStatus: "matched",
        limit: 20,
        offset: 20,
        sortBy: "user_id",
        order: "desc",
      });
      expect(screen.getByPlaceholderText("User ID")).toHaveValue("7");
      expect(screen.getByPlaceholderText("Name / email")).toHaveValue("ali");
      expect(screen.getByLabelText("Account")).toHaveTextContent("Blocked");
      expect(screen.getByLabelText("Internal or external")).toHaveTextContent(
        "External",
      );
      expect(screen.getByLabelText("Onboarding status")).toHaveTextContent(
        "Training done",
      );
      expect(screen.getByLabelText("Round")).toHaveTextContent("Spring 2026");
    });

    it("ignores URL values the backend would reject", async () => {
      await renderCard({
        url: "/?round=7&id=abc&account=suspended&internal=x&training=y",
      });
      await mounted();

      const args = searchParticipants.mock.calls[0][0];
      expect(args.userId).toBeUndefined();
      expect(args.accountStatus).toBeUndefined();
      expect(args.internal).toBeUndefined();
      expect(args.onboardingStatus).toBeUndefined();
    });

    it("does not search when a filter changes", async () => {
      await renderCard();
      await act(async () => {});

      await userEvent.type(screen.getByPlaceholderText("User ID"), "12");
      await userEvent.type(screen.getByPlaceholderText("Name / email"), "ali");
      await userEvent.click(screen.getByLabelText("Account"));
      await userEvent.click(screen.getByRole("option", { name: "Blocked" }));
      await userEvent.click(screen.getByLabelText("Internal or external"));
      await userEvent.click(screen.getByRole("option", { name: "Internal" }));
      await userEvent.click(screen.getByLabelText("Onboarding status"));
      await userEvent.click(
        screen.getByRole("option", { name: "Training done" }),
      );

      expect(searchParticipants).not.toHaveBeenCalled();
      expect(screen.getByTestId("location-search").textContent).toBe("");
    });

    it("does not search when a filter changes after a search has run", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();

      await userEvent.type(screen.getByPlaceholderText("Name / email"), "ali");
      await userEvent.click(screen.getByLabelText("Account"));
      await userEvent.click(screen.getByRole("option", { name: "Active" }));

      expect(searchParticipants).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("location-search").textContent).toBe(
        "?round=7",
      );
    });

    it("does not search when Enter is pressed in a text box", async () => {
      await renderCard();
      await act(async () => {});

      await userEvent.type(
        screen.getByPlaceholderText("Name / email"),
        "ali{Enter}",
      );
      await userEvent.type(screen.getByPlaceholderText("User ID"), "3{Enter}");

      expect(searchParticipants).not.toHaveBeenCalled();
      expect(screen.getByTestId("location-search").textContent).toBe("");
    });

    it("searches with the inputs and writes them to the URL when Search is clicked", async () => {
      await renderCard();
      await act(async () => {});

      await userEvent.type(screen.getByPlaceholderText("User ID"), "42");
      await userEvent.type(screen.getByPlaceholderText("Name / email"), "Ali");
      await userEvent.click(screen.getByLabelText("Account"));
      await userEvent.click(
        screen.getByRole("option", { name: "Deactivated" }),
      );
      await userEvent.click(screen.getByLabelText("Internal or external"));
      await userEvent.click(screen.getByRole("option", { name: "Internal" }));
      await userEvent.click(screen.getByLabelText("Onboarding status"));
      await userEvent.click(
        screen.getByRole("option", { name: "Training not done" }),
      );
      await userEvent.click(screen.getByLabelText("Round"));
      await userEvent.click(
        screen.getByRole("option", { name: "Spring 2026" }),
      );
      await search();

      await mounted();
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({
          userId: "42",
          q: "Ali",
          accountStatus: "deactivated",
          internal: "internal",
          onboardingStatus: "incomplete",
          roundId: "3",
          offset: 0,
        }),
      );
      const params = urlParams();
      expect(params.get("id")).toBe("42");
      expect(params.get("q")).toBe("Ali");
      expect(params.get("account")).toBe("deactivated");
      expect(params.get("internal")).toBe("internal");
      expect(params.get("training")).toBe("incomplete");
      expect(params.get("round")).toBe("3");
      expect(params.has("offset")).toBe(false);
    });

    it("searching again with nothing changed re-reads the list", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();

      await search();
      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(2));
      await search();
      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(3));
    });

    it("a new search returns to the first page", async () => {
      await renderCard({ url: "/?round=7&offset=40" });
      await mounted();

      await userEvent.type(screen.getByPlaceholderText("Name / email"), "x");
      await search();

      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ q: "x", offset: 0 }),
        ),
      );
      expect(urlParams().has("offset")).toBe(false);
    });

    it("going back restores the previous search and inputs from the URL", async () => {
      await renderCard({ url: "/?round=7&q=ann" });
      await mounted();

      await userEvent.clear(screen.getByPlaceholderText("Name / email"));
      await userEvent.type(screen.getByPlaceholderText("Name / email"), "ben");
      await search();
      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(2));

      act(() => navigateTo(-1));

      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(3));
      expect(searchParticipants.mock.calls[2][0].q).toBe("ann");
      expect(screen.getByPlaceholderText("Name / email")).toHaveValue("ann");
    });

    it("going back to a URL with no search empties the list without a request", async () => {
      await renderCard();
      await userEvent.type(screen.getByPlaceholderText("Name / email"), "ali");
      await search();
      await mounted();

      act(() => navigateTo(-1));

      expect(
        await screen.findByText(
          "Set filters and click Search to see participants.",
        ),
      ).toBeInTheDocument();
      expect(searchParticipants).toHaveBeenCalledTimes(1);
      expect(screen.getByPlaceholderText("Name / email")).toHaveValue("");
    });

    it("coming back from a round's feedback page restores the search", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      getRoundFeedback.mockResolvedValue({
        data: {
          roundId: 7,
          roundName: "Mentorship 2026 Fall",
          owed: 1,
          sent: 0,
          participants: [],
        },
      });
      render(
        <MemoryRouter initialEntries={["/mentorship-management?round=7&q=ali"]}>
          <Routes>
            <Route
              path="/mentorship-management"
              element={
                <>
                  <AllRoundsTable
                    rounds={[
                      {
                        id: 7,
                        name: "Mentorship 2026 Fall",
                        feedbackOwed: 1,
                        feedbackSent: 0,
                      },
                    ]}
                    totals={{}}
                    onEdit={vi.fn()}
                    canReadFeedback
                  />
                  <ParticipantSearchCard />
                </>
              }
            />
            <Route
              path="/mentorship-management/rounds/:roundId/feedback"
              element={<RoundFeedbackPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
      await mounted();

      await userEvent.click(
        screen.getByRole("link", { name: "Feedback for Mentorship 2026 Fall" }),
      );
      await userEvent.click(
        await screen.findByRole("link", { name: "Mentorship Management" }),
      );

      expect(await screen.findByText("Alice Doe")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Name / email")).toHaveValue("ali");
      expect(searchParticipants).toHaveBeenCalledTimes(2);
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({
          q: "ali",
        }),
      );
    });

    it("paging moves within the committed search and keeps it in the URL", async () => {
      searchParticipants.mockResolvedValue({
        data: { participantRows: [participantRow()], total: 45 },
      });
      await renderCard({ url: "/?round=7&q=ali" });
      await mounted();

      // A draft that was never searched does not ride along with paging.
      await userEvent.type(screen.getByPlaceholderText("User ID"), "9");
      await userEvent.click(screen.getByRole("button", { name: "Next" }));

      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ q: "ali", offset: 20, userId: undefined }),
        ),
      );
      expect(urlParams().get("offset")).toBe("20");
      expect(urlParams().get("q")).toBe("ali");
      expect(urlParams().has("id")).toBe(false);
    });
  });

  describe("inputs", () => {
    it("has one User ID box and one Name / email box, and no separate name, email or matched user boxes", async () => {
      await renderCard();
      expect(screen.getByPlaceholderText("User ID")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Name / email")).toBeInTheDocument();
      expect(screen.queryByPlaceholderText("Name")).not.toBeInTheDocument();
      expect(screen.queryByPlaceholderText("Email")).not.toBeInTheDocument();
      expect(
        screen.queryByPlaceholderText("Matched User Name"),
      ).not.toBeInTheDocument();
    });

    it("labels the account, internal and training filters", async () => {
      await renderCard();
      expect(screen.getByLabelText("Account")).toHaveTextContent("Any account");
      expect(screen.getByLabelText("Internal or external")).toHaveTextContent(
        "Internal & external",
      );
      expect(screen.getByLabelText("Onboarding status")).toHaveTextContent(
        "Any training",
      );

      await userEvent.click(screen.getByLabelText("Account"));
      ["Any account", "Active", "Blocked", "Deactivated"].forEach((name) =>
        expect(screen.getByRole("option", { name })).toBeInTheDocument(),
      );
    });

    it("strips non-digits from the User ID field", async () => {
      await renderCard();
      const idInput = screen.getByPlaceholderText("User ID");
      await userEvent.type(idInput, "a1b2c3");
      expect(idInput).toHaveValue("123");
    });

    it("is titled Participants and has the Round filter in its header", async () => {
      await renderCard();
      const header = screen
        .getByText("Participants")
        .closest('[data-slot="card-header"]');
      expect(header).not.toBeNull();
      expect(within(header).getByLabelText("Round")).toBeInTheDocument();
      expect(screen.queryByText("Participant Search")).not.toBeInTheDocument();
    });

    it("has no Non-participants tab", async () => {
      await renderCard();
      expect(screen.queryByRole("tab")).not.toBeInTheDocument();
      expect(screen.queryByText("Non-participants")).not.toBeInTheDocument();
    });

    it("lays out the filter bar in order, with List last, then Search", async () => {
      await renderCard();
      const bar = screen.getByLabelText("User ID").parentElement;
      expect(
        Array.from(bar.querySelectorAll("[aria-label]")).map((el) =>
          el.getAttribute("aria-label"),
        ),
      ).toEqual([
        "User ID",
        "Name / email",
        "Role",
        "Internal or external",
        "Account",
        "Onboarding status",
        "Approval status",
        "List",
      ]);
      expect(Array.from(bar.children).at(-1)).toBe(
        screen.getByRole("button", { name: "Search" }),
      );
      expect(
        screen.queryByRole("button", { name: "Not registered" }),
      ).not.toBeInTheDocument();
    });

    it("no longer sends a participation status", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();
      expect(searchParticipants.mock.calls[0][0]).not.toHaveProperty(
        "participationStatus",
      );
    });

    it("lists the given rounds by name, with no all-rounds option, and sends the selected round's id", async () => {
      await renderCard();

      await userEvent.click(screen.getByLabelText("Round"));
      expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
        "Fall 2026",
        "Spring 2026",
      ]);
      await userEvent.click(
        screen.getByRole("option", { name: "Spring 2026" }),
      );
      await search();

      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ roundId: "3" }),
        ),
      );
    });

    it("selects the first round listed, not the lowest id", async () => {
      await renderCard();
      expect(screen.getByLabelText("Round")).toHaveTextContent("Fall 2026");
    });

    it("keeps Search disabled until the rounds have loaded", async () => {
      let resolveRounds;
      getAllMentorshipRounds.mockReturnValue(
        new Promise((resolve) => {
          resolveRounds = resolve;
        }),
      );
      render(
        <MemoryRouter>
          <ParticipantSearchCard />
        </MemoryRouter>,
      );
      expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();

      await act(async () => resolveRounds({ data: TEST_ROUNDS }));
      expect(screen.getByRole("button", { name: "Search" })).toBeEnabled();
      expect(screen.getByLabelText("Round")).toHaveTextContent("Fall 2026");
    });

    it("does not fetch a search from the URL until the rounds load", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS, rounds: null });
      await act(async () => {});
      expect(searchParticipants).not.toHaveBeenCalled();
    });

    it("treats a URL without a round as no search", async () => {
      await renderCard({ url: "/?q=ali" });
      await act(async () => {});
      expect(searchParticipants).not.toHaveBeenCalled();
      expect(
        screen.getByText("Set filters and click Search to see participants."),
      ).toBeInTheDocument();
    });

    it("reads a round that is not a number as the latest round and writes it back", async () => {
      await renderCard({ url: "/?round=abc&q=ali" });
      await mounted();

      expect(searchParticipants.mock.calls[0][0]).toMatchObject({
        q: "ali",
        roundId: "7",
      });
      await waitFor(() => expect(urlParams().get("round")).toBe("7"));
      expect(urlParams().get("q")).toBe("ali");
    });

    it("says there are no rounds instead of an empty dropdown, with Search disabled", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS, rounds: [] });
      await act(async () => {});

      expect(screen.getByText("No mentorship rounds yet.")).toBeInTheDocument();
      expect(screen.queryByLabelText("Round")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
      expect(searchParticipants).not.toHaveBeenCalled();
    });

    it("reads a round id that is not listed as the latest round", async () => {
      await renderCard({ url: "/?round=99" });
      await mounted();

      expect(searchParticipants.mock.calls[0][0].roundId).toBe("7");
      await waitFor(() => expect(urlParams().get("round")).toBe("7"));
      expect(screen.getByLabelText("Round")).toHaveTextContent("Fall 2026");
    });

    it("replaces the unresolved link in history instead of adding an entry", async () => {
      render(
        <MemoryRouter initialEntries={["/start", "/?round=99"]}>
          <Routes>
            <Route path="/start" element={<div>start page</div>} />
            <Route path="/" element={<ParticipantSearchCard />} />
          </Routes>
          <LocationProbe />
        </MemoryRouter>,
      );
      await waitFor(() => expect(urlParams().get("round")).toBe("7"));

      act(() => navigateTo(-1));
      expect(await screen.findByText("start page")).toBeInTheDocument();
    });

    it("sends the selected approval status filter in participant mode", async () => {
      await renderCard();

      await userEvent.click(screen.getByLabelText("Approval status"));
      await userEvent.click(screen.getByRole("option", { name: "Matched" }));
      await search();

      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ approvalStatus: "matched" }),
        ),
      );
      expect(urlParams().get("approval")).toBe("matched");
    });

    it("can filter on people withdrawn from the round", async () => {
      await renderCard();

      await userEvent.click(screen.getByLabelText("Approval status"));
      await userEvent.click(screen.getByRole("option", { name: "Withdrawn" }));
      await search();

      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ approvalStatus: "withdrawn" }),
        ),
      );
      expect(urlParams().get("approval")).toBe("withdrawn");
    });

    it("has no export control", async () => {
      await renderCard();
      expect(
        screen.queryByRole("button", { name: /export/i }),
      ).not.toBeInTheDocument();
    });
  });

  describe("columns", () => {
    it("renders the participant column headers in order", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Alice Doe");

      expect(
        screen.getAllByRole("columnheader").map((th) => th.textContent),
      ).toEqual([
        "Name",
        "Role",
        "Training",
        "Int / ext",
        "Approval",
        "Account",
        "Pair",
      ]);
    });

    it("shows each row's own account state and internal flag", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({ userId: 1, preferredName: "Ann" }),
          participantRow({
            userId: 2,
            preferredName: "Ben",
            isBlocked: true,
          }),
          participantRow({
            userId: 3,
            preferredName: "Cal",
            isDeactivated: true,
          }),
          participantRow({
            userId: 4,
            preferredName: "Dee",
            isInternal: true,
          }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const rowOf = async (name) =>
        within((await screen.findByText(name)).closest("tr"));

      const ann = await rowOf("Ann");
      expect(ann.getByText("Active")).toBeInTheDocument();
      expect(ann.getByText("External")).toBeInTheDocument();

      const ben = await rowOf("Ben");
      expect(ben.getByText("Blocked")).toBeInTheDocument();
      expect(ben.queryByText("Active")).not.toBeInTheDocument();
      expect(ben.queryByText("Deactivated")).not.toBeInTheDocument();

      const cal = await rowOf("Cal");
      expect(cal.getByText("Deactivated")).toBeInTheDocument();
      expect(cal.queryByText("Blocked")).not.toBeInTheDocument();
      expect(cal.queryByText("Active")).not.toBeInTheDocument();

      const dee = await rowOf("Dee");
      expect(dee.getByText("Internal")).toBeInTheDocument();
      expect(dee.getByText("Active")).toBeInTheDocument();

      expect(screen.queryByText("Block requested")).not.toBeInTheDocument();
    });

    it("names the person with their display name over their user ID and email", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const name = await screen.findByText("Alice Doe");
      const cell = cellOf(name, "Name");
      expect(within(cell).getByText("ID 11 · alice@x.com")).toBeInTheDocument();
      const link = within(cell).getByRole("link", { name: "Alice Doe" });
      expect(link).toHaveAttribute(
        "href",
        "/mentorship-management/participants/11?round=7",
      );
    });

    it("carries the list's search to the detail page for Back", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      getAllMentorshipRounds.mockResolvedValue({ data: TEST_ROUNDS });
      const view = render(
        <MemoryRouter initialEntries={["/?round=7&q=alice"]}>
          <Routes>
            <Route path="/" element={<ParticipantSearchCard />} />
            <Route
              path="/mentorship-management/participants/:userId"
              element={<StateProbe />}
            />
          </Routes>
        </MemoryRouter>,
      );
      await userEvent.click(
        await view.findByRole("link", { name: "Alice Doe" }),
      );
      expect(screen.getByTestId("return-search")).toHaveTextContent(
        "?round=7&q=alice",
      );
    });

    it("leaves the email off the ID line when there is none", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({
            preferredName: null,
            firstName: "Carol",
            lastName: "Jones",
            primaryEmail: null,
          }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const name = await screen.findByText("Carol Jones");
      expect(
        within(cellOf(name, "Name")).getByText("ID 11"),
      ).toBeInTheDocument();
      expect(
        screen.queryByText("null", { exact: false }),
      ).not.toBeInTheDocument();
    });

    it("renders the rest of a participant row", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const name = await screen.findByText("Alice Doe");
      expect(cellOf(name, "Role")).toHaveTextContent("mentor");
      expect(cellOf(name, "Int / ext")).toHaveTextContent("External");
      expect(cellOf(name, "Approval")).toHaveTextContent("matched");
    });

    it("shows the pair's partner, their ID and the meeting progress", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const pair = cellOf(await screen.findByText("Alice Doe"), "Pair");
      expect(
        within(pair).getByRole("link", { name: "with Bob Smith (22)" }),
      ).toHaveAttribute(
        "href",
        "/mentorship-management/participants/22?round=7&pair=80",
      );
      expect(
        within(pair).getByRole("button", { name: "Meetings 2/5" }),
      ).toBeInTheDocument();
    });

    it("lists every pair in one row, active first and ended after", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({
            pairs: [
              pairOf({
                pairId: 81,
                id: 5862,
                name: "Bea Marlow",
                isActive: false,
                completedMeetingCount: 1,
              }),
              pairOf({
                pairId: 82,
                id: 5863,
                name: "Cid Nash",
                completedMeetingCount: 3,
              }),
            ],
          }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      expect(screen.getAllByRole("row")).toHaveLength(2);
      const pair = cellOf(await screen.findByText("Alice Doe"), "Pair");
      const items = within(pair).getAllByRole("listitem");
      expect(items.map((li) => li.getAttribute("aria-label"))).toEqual([
        "Pair Alice Doe and Cid Nash",
        "Pair Alice Doe and Bea Marlow",
      ]);
      expect(items[0]).toHaveTextContent("with Cid Nash (5863)");
      expect(within(items[0]).queryByText("Ended")).not.toBeInTheDocument();
      expect(
        within(items[0]).getByRole("button", { name: "Meetings 3/5" }),
      ).toBeInTheDocument();
      expect(items[1]).toHaveTextContent("with Bea Marlow (5862)");
      expect(within(items[1]).getByText("Ended")).toBeInTheDocument();
      expect(
        within(items[1]).getByRole("button", { name: "Meetings 1/5" }),
      ).toBeInTheDocument();
    });

    it("names a mentee's mentor first in the pair's label", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([participantRow({ participantRole: "mentee" })]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const pair = cellOf(await screen.findByText("Alice Doe"), "Pair");
      expect(within(pair).getByRole("listitem")).toHaveAttribute(
        "aria-label",
        "Pair Bob Smith and Alice Doe",
      );
    });

    it("shows a dash in Pair when there is no pair", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([participantRow({ pairs: [] })]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const pair = cellOf(await screen.findByText("Alice Doe"), "Pair");
      expect(pair).toHaveTextContent(/^—$/);
    });
  });

  describe("status and pair", () => {
    const endedPair = pairOf({ isActive: false });

    it("shows rejected as stored, even when the participant holds a pairing", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({
            approvalStatus: "rejected",
            pairs: [endedPair],
          }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const status = await screen.findByText("rejected");
      expect(cellOf(status, "Approval")).toContainElement(status);
      expect(screen.queryByText("ended")).not.toBeInTheDocument();
    });

    it("shows a dash in Approval when there is no approval status", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([participantRow({ approvalStatus: null })]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const name = await screen.findByText("Alice Doe");
      expect(cellOf(name, "Approval")).toHaveTextContent(/^—$/);
    });

    it("marks the partner of a pairing that has ended", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([participantRow({ pairs: [endedPair] })]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const pair = cellOf(await screen.findByText("Alice Doe"), "Pair");
      expect(within(pair).getByText("with Bob Smith (22)")).toBeInTheDocument();
      expect(within(pair).getByText("Ended")).toBeInTheDocument();
    });

    it("does not mark a partner whose pairing is live", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      expect(
        await screen.findByText("with Bob Smith (22)"),
      ).toBeInTheDocument();
      expect(screen.queryByText("Ended")).not.toBeInTheDocument();
    });
  });

  describe("attendance", () => {
    const flagged = [
      { startDatetime: "2026-08-30T17:00:00Z", note: ["mentee_absent"] },
      {
        startDatetime: "2026-09-13T17:00:00Z",
        note: ["mentor_late", "insufficient_duration"],
      },
    ];
    const markOf = (lines) => ({
      name: `Attendance issues: ${lines.join(", ")}`,
    });

    it("marks a live pair with flagged meetings and lists them on focus", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({ pairs: [pairOf({ attendanceIssues: flagged })] }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const pair = cellOf(await screen.findByText("Alice Doe"), "Pair");
      const lines = [
        "2026-08-30: Bob Smith absent",
        "2026-09-13: Alice Doe late arrival; Insufficient duration",
      ];
      const mark = within(pair).getByRole("button", markOf(lines));
      expect(within(pair).getByRole("listitem")).toHaveClass("text-red-700");

      mark.focus();

      for (const line of lines) {
        expect((await screen.findAllByText(line)).length).toBeGreaterThan(0);
      }
    });

    it("does not mark an ended pair, flagged or not", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({
            pairs: [pairOf({ isActive: false, attendanceIssues: flagged })],
          }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const pair = cellOf(await screen.findByText("Alice Doe"), "Pair");
      expect(
        within(pair).queryByRole("button", { name: /^Attendance issues/ }),
      ).not.toBeInTheDocument();
      expect(within(pair).getByRole("listitem")).not.toHaveClass(
        "text-red-700",
      );
    });

    it("reddens only the flagged pair, not its neighbour or the row", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({
            pairs: [
              pairOf({ pairId: 81, id: 5862, name: "Bea Marlow" }),
              pairOf({
                pairId: 82,
                id: 5863,
                name: "Cid Nash",
                attendanceIssues: [flagged[0]],
              }),
            ],
          }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const name = await screen.findByText("Alice Doe");
      const [bea, cid] = within(cellOf(name, "Pair")).getAllByRole("listitem");
      expect(bea).not.toHaveClass("text-red-700");
      expect(
        within(bea).queryByRole("button", { name: /^Attendance issues/ }),
      ).not.toBeInTheDocument();
      expect(cid).toHaveClass("text-red-700");
      expect(
        within(cid).getByRole(
          "button",
          markOf(["2026-08-30: Cid Nash absent"]),
        ),
      ).toBeInTheDocument();
      expect(name.closest("tr").className).not.toMatch(/red/);
    });
  });

  describe("not registered", () => {
    const unregisteredRow = (overrides = {}) => ({
      userId: 31,
      firstName: "Dana",
      lastName: "Wu",
      preferredName: "Dana Wu",
      primaryEmail: "dana@x.com",
      alternativeEmails: [],
      isBlocked: false,
      isDeactivated: true,
      isInternal: true,
      admittedRoles: ["mentor", "mentee"],
      roundsTakenPart: 3,
      lastRoundName: "Spring 2026",
      ...overrides,
    });

    const pickList = async (name) => {
      await userEvent.click(screen.getByLabelText("List"));
      await userEvent.click(screen.getByRole("option", { name }));
    };

    it("defaults the List filter to Registered", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();
      expect(screen.getByLabelText("List")).toHaveTextContent("Registered");
    });

    it("greys out Not registered, with no hint, for a round not in progress", async () => {
      await renderCard({ url: "/?round=3" });
      await mounted();

      await userEvent.click(screen.getByLabelText("List"));
      const option = screen.getByRole("option", { name: "Not registered" });

      expect(option).toHaveAttribute("aria-disabled", "true");
      expect(option).toHaveTextContent(/^Not registered$/);
    });

    it("does not switch lists until Search, and greys out training and approval as soon as it is picked", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      searchUnregistered.mockResolvedValue({
        data: { rows: [unregisteredRow()], total: 1 },
      });
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Alice Doe");

      await pickList("Not registered");

      expect(screen.getByLabelText("Onboarding status")).toBeDisabled();
      expect(screen.getByLabelText("Approval status")).toBeDisabled();
      expect(searchUnregistered).not.toHaveBeenCalled();
      expect(urlParams().has("notRegistered")).toBe(false);
      expect(screen.getByText("Alice Doe")).toBeInTheDocument();

      await search();

      expect(await screen.findByText("Dana Wu")).toBeInTheDocument();
      expect(urlParams().get("notRegistered")).toBe("1");
    });

    it("goes back to Registered when a round not in progress is picked", async () => {
      searchUnregistered.mockResolvedValue({
        data: { rows: [unregisteredRow()], total: 1 },
      });
      await renderCard({ url: "/?round=7&notRegistered=1" });
      await screen.findByText("Dana Wu");
      expect(screen.getByLabelText("List")).toHaveTextContent("Not registered");

      await userEvent.click(screen.getByLabelText("Round"));
      await userEvent.click(
        screen.getByRole("option", { name: "Spring 2026" }),
      );

      expect(screen.getByLabelText("List")).toHaveTextContent(/^Registered$/);
      expect(screen.getByLabelText("Onboarding status")).toBeEnabled();
    });

    it("explains Rounds taken part in its header", async () => {
      searchUnregistered.mockResolvedValue({
        data: { rows: [unregisteredRow()], total: 1 },
      });
      await renderCard({ url: "/?round=7&notRegistered=1" });
      await screen.findByText("Dana Wu");

      screen.getByText("Rounds taken part").focus();

      expect(
        (
          await screen.findAllByText(
            "Every round the person registered for, including rounds where they were not matched or stopped early.",
          )
        ).length,
      ).toBeGreaterThan(0);
    });

    it("links each name to the person's page in the selected round", async () => {
      searchUnregistered.mockResolvedValue({
        data: { rows: [unregisteredRow()], total: 1 },
      });
      await renderCard({ url: "/?round=7&notRegistered=1" });

      const link = await screen.findByRole("link", { name: "Dana Wu" });
      expect(link.getAttribute("href")).toBe(
        "/mentorship-management/participants/31?round=7",
      );
    });

    it("swaps the table for the not registered people of the round", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      searchUnregistered.mockResolvedValue({
        data: {
          rows: [
            unregisteredRow(),
            unregisteredRow({
              userId: 32,
              preferredName: "Eli Fox",
              isDeactivated: false,
              isInternal: false,
              admittedRoles: ["mentee"],
              roundsTakenPart: 0,
              lastRoundName: null,
            }),
          ],
          total: 2,
        },
      });
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Alice Doe");

      await pickList("Not registered");
      await search();

      const dana = await screen.findByText("Dana Wu");
      expect(searchUnregistered.mock.calls[0][0]).toBe("7");
      expect(urlParams().get("notRegistered")).toBe("1");
      expect(
        within(dana.closest("table"))
          .getAllByRole("columnheader")
          .map((th) => th.textContent),
      ).toEqual([
        expect.stringContaining("Name"),
        "Admitted as",
        "Int / ext",
        "Account",
        "Rounds taken part",
        "Last round",
      ]);
      expect(cellOf(dana, "Admitted as")).toHaveTextContent(/^mentor, mentee$/);
      expect(cellOf(dana, "Int / ext")).toHaveTextContent("Internal");
      expect(cellOf(dana, "Account")).toHaveTextContent("Deactivated");
      expect(cellOf(dana, "Rounds taken part")).toHaveTextContent(/^3$/);
      expect(cellOf(dana, "Last round")).toHaveTextContent("Spring 2026");
      const eli = screen.getByText("Eli Fox");
      expect(cellOf(eli, "Admitted as")).toHaveTextContent(/^mentee$/);
      expect(cellOf(eli, "Rounds taken part")).toHaveTextContent(/^0$/);
      expect(cellOf(eli, "Last round")).toHaveTextContent("Never");
      expect(screen.queryByText("Alice Doe")).not.toBeInTheDocument();
    });

    it("greys out the training and approval filters while it is on", async () => {
      searchUnregistered.mockResolvedValue({
        data: { rows: [unregisteredRow()], total: 1 },
      });
      await renderCard({ url: "/?round=7&notRegistered=1" });
      await screen.findByText("Dana Wu");

      expect(screen.getByLabelText("Onboarding status")).toBeDisabled();
      expect(screen.getByLabelText("Approval status")).toBeDisabled();
      expect(screen.getByLabelText("Role")).toBeEnabled();
      expect(searchParticipants).not.toHaveBeenCalled();
    });
  });

  describe("eligible for matching", () => {
    const ROUNDS = [
      {
        id: 7,
        name: "Fall 2026",
        isInProgress: true,
        timeline: {},
      },
      {
        id: 3,
        name: "Spring 2026",
        isInProgress: false,
        timeline: {
          promotionStartAt: "2026-02-01T20:00:00Z",
          feedbackDeadlineAt: "2026-07-01T20:00:00Z",
        },
      },
    ];

    const pickList = async (name) => {
      await userEvent.click(screen.getByLabelText("List"));
      await userEvent.click(screen.getByRole("option", { name }));
    };

    it("lists only the eligible when picked and Search is clicked", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS, rounds: ROUNDS });
      await mounted();

      await pickList("Eligible for matching");
      expect(screen.getByLabelText("List")).toHaveTextContent(
        "Eligible for matching",
      );
      expect(searchParticipants).toHaveBeenCalledTimes(1);
      expect(urlParams().has("eligible")).toBe(false);

      await search();

      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(2));
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ roundId: "7", eligible: true }),
      );
      expect(urlParams().get("eligible")).toBe("1");
      expect(screen.getByLabelText("Onboarding status")).toBeEnabled();
    });

    it("picking Registered and searching lists everyone again", async () => {
      await renderCard({ url: "/?round=7&eligible=1", rounds: ROUNDS });
      await mounted();
      expect(screen.getByLabelText("List")).toHaveTextContent(
        "Eligible for matching",
      );

      await pickList("Registered");
      await search();

      await waitFor(() => expect(urlParams().has("eligible")).toBe(false));
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ eligible: undefined }),
      );
    });

    it("greys out Eligible, with no hint, for a round not in progress", async () => {
      await renderCard({ url: "/?round=3", rounds: ROUNDS });
      await mounted();

      await userEvent.click(screen.getByLabelText("List"));
      const option = screen.getByRole("option", {
        name: "Eligible for matching",
      });

      expect(option).toHaveAttribute("aria-disabled", "true");
      expect(option).toHaveTextContent(/^Eligible for matching$/);
    });

    it("moving from Eligible to Not registered switches lists on Search", async () => {
      searchUnregistered.mockResolvedValue({ data: { rows: [], total: 0 } });
      await renderCard({ url: "/?round=7&eligible=1", rounds: ROUNDS });
      await mounted();

      await pickList("Not registered");
      await search();

      await waitFor(() => expect(urlParams().get("notRegistered")).toBe("1"));
      expect(urlParams().has("eligible")).toBe(false);
      expect(searchUnregistered).toHaveBeenCalled();
    });
  });

  describe("training", () => {
    const trainingOf = async (row) => {
      searchParticipants.mockResolvedValue(resultsOf([row]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      return cellOf(await screen.findByText("Alice Doe"), "Training");
    };

    it("reads a mentor's mentor course", async () => {
      const cell = await trainingOf(
        participantRow({
          participantRole: "mentor",
          mentorOnboardingStatus: "done",
          menteeOnboardingStatus: "to_do",
        }),
      );
      expect(cell).toHaveTextContent(/^Done$/);
    });

    it("reads a mentee's mentee course", async () => {
      const cell = await trainingOf(
        participantRow({
          participantRole: "mentee",
          mentorOnboardingStatus: "done",
          menteeOnboardingStatus: "to_do",
        }),
      );
      expect(cell).toHaveTextContent(/^Not done$/);
    });

    it("reads a course in progress as not done", async () => {
      const cell = await trainingOf(
        participantRow({ mentorOnboardingStatus: "in_progress" }),
      );
      expect(cell).toHaveTextContent(/^Not done$/);
    });

    it("says No course when the role has no course", async () => {
      const cell = await trainingOf(
        participantRow({
          participantRole: "mentor",
          mentorOnboardingStatus: null,
          menteeOnboardingStatus: "done",
        }),
      );
      expect(cell).toHaveTextContent(/^No course$/);
    });
  });

  describe("results table", () => {
    it("keeps the table and pager mounted while a search is loading", async () => {
      let resolveFetch;
      searchParticipants.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveFetch = resolve;
          }),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();

      expect(
        screen.getByRole("columnheader", { name: "Name" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Prev" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();

      await act(async () => {
        resolveFetch(resultsOf([participantRow()]));
      });
      expect(await screen.findByText("Alice Doe")).toBeInTheDocument();
    });
  });

  describe("sorting", () => {
    const nameHeader = () => screen.getByRole("columnheader", { name: "Name" });

    it("clicking the Name header sorts ascending, then descending, and keeps it in the URL", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();

      await userEvent.click(nameHeader());
      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ sortBy: "user_id", order: "asc" }),
        ),
      );
      expect(urlParams().get("sort")).toBe("user_id");

      await userEvent.click(nameHeader());
      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ sortBy: "user_id", order: "desc" }),
        ),
      );
      expect(urlParams().get("order")).toBe("desc");
    });

    it("clicking the Name header a third time clears the sort back to the default order", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({
        url: "/?round=7&sort=user_id&order=desc&offset=20",
      });
      await mounted();

      await userEvent.click(nameHeader());
      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ sortBy: undefined, offset: 0 }),
        ),
      );
      expect(urlParams().has("sort")).toBe(false);
      expect(urlParams().has("offset")).toBe(false);
    });

    it("clicking a non-sortable column header does not trigger a new fetch", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();

      await userEvent.click(screen.getByRole("columnheader", { name: "Role" }));
      expect(searchParticipants).toHaveBeenCalledTimes(1);
    });
  });

  describe("meetings", () => {
    it("opens a past round's meeting log read-only", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      getMeetingLog.mockResolvedValue({
        data: {
          ...meetingLogResponse("v2", "gm-80-1").data,
          roundInProgress: false,
        },
      });
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      await userEvent.click(
        await screen.findByRole("button", { name: "Meetings 2/5" }),
      );

      await screen.findByText("2024-03-01 · 15:30 - 16:30");
      expect(
        screen.queryByRole("button", { name: "Edit" }),
      ).not.toBeInTheDocument();
    });

    it("opens the meeting log from the button in the Pair cell", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      const link = await screen.findByRole("button", { name: "Meetings 2/5" });
      expect(getMeetingLog).not.toHaveBeenCalled();

      await userEvent.click(link);

      expect(
        screen.getByText(
          "Meeting Log — Alice Doe (Mentor) with Bob Smith (Mentee) · Spring 2026",
        ),
      ).toBeInTheDocument();
      await waitFor(() => expect(getMeetingLog).toHaveBeenCalledWith(80));
    });

    it("opens each pair's own meeting log from its own button", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({
            pairs: [
              pairOf({ pairId: 81, id: 5862, name: "Bea Marlow" }),
              pairOf({
                pairId: 82,
                id: 5863,
                name: "Cid Nash",
                completedMeetingCount: 4,
              }),
            ],
          }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      await userEvent.click(
        await screen.findByRole("button", { name: "Meetings 4/5" }),
      );
      expect(
        screen.getByText(
          "Meeting Log — Alice Doe (Mentor) with Cid Nash (Mentee) · Spring 2026",
        ),
      ).toBeInTheDocument();
      await waitFor(() => expect(getMeetingLog).toHaveBeenCalledWith(82));

      await userEvent.keyboard("{Escape}");
      await waitFor(() =>
        expect(screen.queryByText(/Meeting Log —/)).not.toBeInTheDocument(),
      );

      await userEvent.click(
        screen.getByRole("button", { name: "Meetings 2/5" }),
      );
      expect(
        screen.getByText(
          "Meeting Log — Alice Doe (Mentor) with Bea Marlow (Mentee) · Spring 2026",
        ),
      ).toBeInTheDocument();
      await waitFor(() => expect(getMeetingLog).toHaveBeenLastCalledWith(81));
    });

    it("re-runs the committed search after a successful save", async () => {
      searchParticipants
        .mockResolvedValueOnce(resultsOf([participantRow()]))
        .mockResolvedValueOnce(
          resultsOf([
            participantRow({ pairs: [pairOf({ completedMeetingCount: 1 })] }),
          ]),
        );
      getMeetingLog.mockResolvedValue(meetingLogResponse("v2", "gm-1"));
      updateMeetingLog.mockResolvedValue({
        data: { roundVersion: "v2", meetings: [] },
      });
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await userEvent.click(
        await screen.findByRole("button", { name: "Meetings 2/5" }),
      );

      await userEvent.click(screen.getByRole("button", { name: "Edit" }));
      await userEvent.click(
        screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
      );
      await userEvent.click(screen.getByRole("button", { name: "Delete (1)" }));
      await userEvent.click(
        screen.getByRole("button", { name: "Confirm changes" }),
      );

      // The dialog stays open after a successful save, so the background
      // table is aria-hidden by Radix; query through that.
      expect(
        await screen.findByRole("button", {
          name: "Meetings 1/5",
          hidden: true,
        }),
      ).toBeInTheDocument();
      expect(searchParticipants).toHaveBeenCalledTimes(2);
    });

    it("renders a plain dash instead of a link when the participant has no pair", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([participantRow({ pairs: [] })]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      await screen.findByText("Alice Doe");
      expect(
        screen.queryByRole("button", { name: /^Meetings / }),
      ).not.toBeInTheDocument();
    });

    it("shows the Edit button for a non-empty v2 pair", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      getMeetingLog.mockResolvedValue(meetingLogResponse("v2", "gm-1"));
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await userEvent.click(
        await screen.findByRole("button", { name: "Meetings 2/5" }),
      );

      expect(
        await screen.findByRole("button", { name: "Edit" }),
      ).toBeInTheDocument();
    });

    it("does not show the Edit button for a v1 pair", async () => {
      searchParticipants.mockResolvedValue(resultsOf([participantRow()]));
      getMeetingLog.mockResolvedValue(meetingLogResponse("v1", "m-1"));
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await userEvent.click(
        await screen.findByRole("button", { name: "Meetings 2/5" }),
      );

      await screen.findByText(/Meeting Log —/);
      expect(
        screen.queryByRole("button", { name: "Edit" }),
      ).not.toBeInTheDocument();
    });

    it("does not fetch the meeting log for every row just from rendering the table", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          participantRow({ userId: 1 }),
          participantRow({ userId: 2, pairs: [pairOf({ pairId: 81 })] }),
        ]),
      );
      await renderCard({ url: SEARCHED_PARTICIPANTS });

      await screen.findAllByRole("button", { name: "Meetings 2/5" });
      expect(getMeetingLog).not.toHaveBeenCalled();
    });
  });

  describe("matching run", () => {
    const ELIGIBLE_URL = "/?round=7&eligible=1";

    const mentor = participantRow({
      userId: 11,
      preferredName: "Alice Doe",
      participantRole: "mentor",
      pairs: [],
    });
    const mentee = participantRow({
      userId: 12,
      firstName: "Cara",
      lastName: "Wang",
      preferredName: "Cara Wang",
      primaryEmail: "cara@x.com",
      participantRole: "mentee",
      pairs: [],
    });

    const flagOn = () =>
      useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });

    const runningOverview = {
      data: {
        status: "running",
        runId: 4,
        startedAt: new Date().toISOString(),
        triggeredByUserId: "5845",
        triggeredByName: "Dev Admin",
        mentorCount: 1,
        menteeCount: 1,
      },
    };

    const runButton = () =>
      screen.getByRole("button", { name: /^Run matching · \d+$/ });

    const pick = (name) =>
      userEvent.click(screen.getByRole("checkbox", { name: `Select ${name}` }));

    beforeEach(() => {
      flagOn();
      searchParticipants.mockResolvedValue(resultsOf([mentor, mentee]));
      // vi.mock("sonner") does not reach the component's copy under Bazel.
      vi.spyOn(toast, "error").mockImplementation(() => {});
    });

    it("gives each row and the header a checkbox in Eligible for matching", async () => {
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");

      expect(
        screen.getByRole("checkbox", { name: "Select Alice Doe" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("checkbox", { name: "Select Cara Wang" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("checkbox", { name: "Select all on this page" }),
      ).toBeInTheDocument();
      expect(runButton()).toHaveTextContent("Run matching · 0");
      expect(runButton()).toBeDisabled();
    });

    it("shows no checkboxes and no run button in the Registered list", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Cara Wang");

      expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Run matching/ }),
      ).not.toBeInTheDocument();
    });

    it("hides the run controls and the results button with the flag off, asking nothing", async () => {
      useFeatureFlags.mockReturnValue({
        [FEATURE_FLAGS.MATCHING_RUN]: false,
      });
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");

      expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Run matching/ }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "View matching results" }),
      ).not.toBeInTheDocument();
      expect(getMatchingRun).not.toHaveBeenCalled();
    });

    it("needs at least one mentor and one mentee to run", async () => {
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");

      await pick("Alice Doe");
      expect(runButton()).toHaveTextContent("Run matching · 1");
      expect(runButton()).toBeDisabled();

      await pick("Cara Wang");
      expect(runButton()).toHaveTextContent("Run matching · 2");
      expect(runButton()).toBeEnabled();
    });

    it("select all picks and unpicks everyone on the page", async () => {
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      const all = screen.getByRole("checkbox", {
        name: "Select all on this page",
      });

      await userEvent.click(all);
      expect(runButton()).toHaveTextContent("Run matching · 2");
      expect(
        screen.getByRole("checkbox", { name: "Select Alice Doe" }),
      ).toBeChecked();

      await userEvent.click(all);
      expect(runButton()).toHaveTextContent("Run matching · 0");
    });

    it("cannot run while the round's run is running", async () => {
      getMatchingRun.mockResolvedValue(runningOverview);
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      await screen.findByRole("button", { name: "Matching running…" });

      await pick("Alice Doe");
      await pick("Cara Wang");

      expect(runButton()).toHaveTextContent("Run matching · 2");
      expect(runButton()).toBeDisabled();
    });

    it("cannot run while the round's result waits for approval to publish", async () => {
      getMatchingRun.mockResolvedValue({
        data: {
          status: "succeeded",
          publishRequest: {
            requestId: 31,
            reviewer: { userId: "8", name: "Rae Kim" },
            raisedBy: { userId: "9", name: "Ada Ng" },
          },
        },
      });
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      await waitFor(() => expect(getMatchingRun).toHaveBeenCalled());

      await pick("Alice Doe");
      await pick("Cara Wang");

      expect(runButton()).toHaveTextContent("Run matching · 2");
      expect(runButton()).toBeDisabled();
    });

    it("asks before running, and Cancel starts nothing", async () => {
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      await pick("Alice Doe");
      await pick("Cara Wang");

      await userEvent.click(runButton());

      const dialog = await screen.findByRole("dialog");
      expect(
        within(dialog).getByText("Run matching for Fall 2026?"),
      ).toBeInTheDocument();
      expect(
        within(dialog).getByText("1 mentors and 1 mentees."),
      ).toBeInTheDocument();

      await userEvent.click(
        within(dialog).getByRole("button", { name: "Cancel" }),
      );
      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );
      expect(startMatchingRun).not.toHaveBeenCalled();
    });

    it("Run starts the run for the picked people and opens its results", async () => {
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      await pick("Alice Doe");
      await pick("Cara Wang");
      await userEvent.click(runButton());

      await userEvent.click(
        within(await screen.findByRole("dialog")).getByRole("button", {
          name: "Run",
        }),
      );

      await waitFor(() =>
        expect(screen.getByTestId("location-path")).toHaveTextContent(
          "/mentorship-management/matching/7",
        ),
      );
      expect(startMatchingRun).toHaveBeenCalledWith({
        roundId: 7,
        participantIds: [11, 12],
      });
    });

    it("says why when the run cannot start, and stays", async () => {
      startMatchingRun.mockRejectedValue({
        response: { data: { message: "A run is already running" } },
      });
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      await pick("Alice Doe");
      await pick("Cara Wang");
      await userEvent.click(runButton());

      await userEvent.click(
        within(await screen.findByRole("dialog")).getByRole("button", {
          name: "Run",
        }),
      );

      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith("A run is already running"),
      );
      expect(screen.getByTestId("location-path")).toHaveTextContent(/^\/$/);
      // The dialog stays open over the list for another try.
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Run matching · 2", hidden: true }),
      ).toBeInTheDocument();
    });

    it("falls back to a generic message when the error has none", async () => {
      startMatchingRun.mockRejectedValue(new Error("network"));
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      await pick("Alice Doe");
      await pick("Cara Wang");
      await userEvent.click(runButton());

      await userEvent.click(
        within(await screen.findByRole("dialog")).getByRole("button", {
          name: "Run",
        }),
      );

      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith(
          "Failed to start the matching run",
        ),
      );
    });

    it("keeps picks across pages and sends them all", async () => {
      searchParticipants.mockImplementation(({ offset }) =>
        Promise.resolve({
          data: {
            participantRows: offset ? [mentee] : [mentor],
            total: 21,
          },
        }),
      );
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Alice Doe");
      await pick("Alice Doe");

      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      await screen.findByText("Cara Wang");
      await pick("Cara Wang");
      expect(runButton()).toHaveTextContent("Run matching · 2");
      expect(runButton()).toBeEnabled();

      await userEvent.click(screen.getByRole("button", { name: "Prev" }));
      await screen.findByText("Alice Doe");
      expect(
        screen.getByRole("checkbox", { name: "Select Alice Doe" }),
      ).toBeChecked();

      await userEvent.click(runButton());
      const dialog = await screen.findByRole("dialog");
      expect(
        within(dialog).getByText("1 mentors and 1 mentees."),
      ).toBeInTheDocument();
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Run" }),
      );
      await waitFor(() =>
        expect(startMatchingRun).toHaveBeenCalledWith({
          roundId: 7,
          participantIds: [11, 12],
        }),
      );
    });

    it("drops the picks when a new search is committed", async () => {
      await renderCard({ url: ELIGIBLE_URL });
      await screen.findByText("Cara Wang");
      await pick("Alice Doe");
      expect(runButton()).toHaveTextContent("Run matching · 1");

      await userEvent.type(screen.getByPlaceholderText("Name / email"), "a");
      await search();

      await waitFor(() => expect(urlParams().get("q")).toBe("a"));
      await screen.findByText("Cara Wang");
      expect(runButton()).toHaveTextContent("Run matching · 0");
      expect(
        screen.getByRole("checkbox", { name: "Select Alice Doe" }),
      ).not.toBeChecked();
    });
  });

  describe("matching results button", () => {
    const resultsButton = (name) => screen.findByRole("button", { name });

    beforeEach(() => {
      useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
    });

    it("is greyed out when the round has no run", async () => {
      await renderCard();

      await waitFor(() => expect(getMatchingRun).toHaveBeenCalledWith("7"));
      expect(await resultsButton("View matching results")).toBeDisabled();
    });

    it("says the run is running, and opens the results page", async () => {
      getMatchingRun.mockResolvedValue({
        data: {
          status: "running",
          runId: 4,
          startedAt: new Date().toISOString(),
          triggeredByUserId: null,
          triggeredByName: null,
          mentorCount: 1,
          menteeCount: 1,
        },
      });
      await renderCard();

      const button = await resultsButton("Matching running…");
      expect(button).toBeEnabled();
      await userEvent.click(button);
      expect(screen.getByTestId("location-path")).toHaveTextContent(
        "/mentorship-management/matching/7",
      );
    });

    it("opens the results of a finished run", async () => {
      getMatchingRun.mockResolvedValue({
        data: { status: "failed", runId: 4, error: "Matcher crashed" },
      });
      await renderCard();

      const button = await resultsButton("View matching results");
      await waitFor(() => expect(button).toBeEnabled());
    });

    it("follows the round picked in the Round select", async () => {
      await renderCard();
      await waitFor(() => expect(getMatchingRun).toHaveBeenCalledWith("7"));

      await userEvent.click(screen.getByLabelText("Round"));
      await userEvent.click(
        screen.getByRole("option", { name: "Spring 2026" }),
      );

      await waitFor(() => expect(getMatchingRun).toHaveBeenLastCalledWith("3"));
    });
  });

  describe("needs exemption", () => {
    const NEEDS_URL = "/?round=7&needsExemption=1";

    const pickList = async (name) => {
      await userEvent.click(screen.getByLabelText("List"));
      await userEvent.click(screen.getByRole("option", { name }));
    };

    const shortOfMeetings = (overrides = {}) =>
      participantRow({
        userId: 21,
        firstName: "Ann",
        lastName: "Lee",
        preferredName: "Ann Lee",
        participantRole: "mentee",
        approvalStatus: "signed_up",
        pairs: [],
        exemptionFindings: [
          {
            reason: "meetings_short",
            roundId: 3,
            roundName: "Spring 2026",
            completed: 2,
            required: 5,
          },
        ],
        exemptionRequest: null,
        ...overrides,
      });

    it("lists those only their history keeps out when picked and searched", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();

      await pickList("Needs exemption");
      await search();

      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(2));
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({
          roundId: "7",
          needsExemption: true,
          eligible: undefined,
        }),
      );
      expect(urlParams().get("needsExemption")).toBe("1");
    });

    it("greys out Needs exemption for a round not in progress", async () => {
      await renderCard({ url: "/?round=3" });
      await mounted();

      await userEvent.click(screen.getByLabelText("List"));

      expect(
        screen.getByRole("option", { name: "Needs exemption" }),
      ).toHaveAttribute("aria-disabled", "true");
    });

    it("says why each person needs one", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          shortOfMeetings(),
          shortOfMeetings({
            userId: 22,
            preferredName: "Bo Ng",
            exemptionFindings: [
              {
                reason: "quit_after_match",
                roundId: 3,
                roundName: "Spring 2026",
              },
            ],
          }),
        ]),
      );
      await renderCard({ url: NEEDS_URL });

      expect(
        await screen.findByText("Meetings short in Spring 2026: 2 of 5"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Quit after being matched in Spring 2026"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("columnheader", { name: "Why" }),
      ).toBeInTheDocument();
    });

    it("says a mark in the searched round is in this round", async () => {
      searchParticipants.mockResolvedValue(
        resultsOf([
          shortOfMeetings({
            exemptionFindings: [
              { reason: "red_flag", roundId: 7, roundName: "Fall 2026" },
            ],
          }),
        ]),
      );
      await renderCard({ url: NEEDS_URL });

      expect(
        await screen.findByText("Red flag in this round"),
      ).toBeInTheDocument();
    });

    it("offers the Exemption column only with the matching-run flag on", async () => {
      searchParticipants.mockResolvedValue(resultsOf([shortOfMeetings()]));
      await renderCard({ url: NEEDS_URL });
      await screen.findByText("Ann Lee");

      expect(
        screen.queryByRole("columnheader", { name: "Exemption" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Request exemption" }),
      ).not.toBeInTheDocument();
    });

    it("asks for an exemption for the person in the round", async () => {
      useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
      searchParticipants.mockResolvedValue(resultsOf([shortOfMeetings()]));
      getMentorshipApprovers.mockResolvedValue({
        data: [{ userId: 8, name: "Rae Kim" }],
      });
      requestMatchingExemption.mockResolvedValue({ data: {} });
      await renderCard({ url: NEEDS_URL });

      await userEvent.click(
        await screen.findByRole("button", { name: "Request exemption" }),
      );
      const dialog = await screen.findByRole("dialog");
      await waitFor(() =>
        expect(
          within(dialog).getByRole("option", { name: "Rae Kim" }),
        ).toBeInTheDocument(),
      );
      await userEvent.selectOptions(
        within(dialog).getByLabelText("Reviewer"),
        "8",
      );
      await userEvent.type(
        within(dialog).getByLabelText("Reason (optional)"),
        "Her mentor left midway",
      );
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Send request" }),
      );

      await waitFor(() =>
        expect(requestMatchingExemption).toHaveBeenCalledWith("7", 21, {
          reviewerId: 8,
          reason: "Her mentor left midway",
        }),
      );
      // The list is read again, quietly, to show the request waiting.
      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(2));
    });

    it("lets the named reviewer decide on the row", async () => {
      useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
      useAuth.mockReturnValue({
        permissions: ["mentorship.admin.read", "mentorship.approve"],
        user: { userId: 8 },
      });
      searchParticipants.mockResolvedValue(
        resultsOf([
          shortOfMeetings({
            exemptionRequest: {
              requestId: 61,
              action: "exempt_matching",
              status: "pending",
              round: { roundId: 7, name: "Fall 2026" },
              targetId: "7:21",
              person: { userId: 21, name: "Ann Lee" },
              raisedBy: { userId: 9, name: "Ada Ng" },
              reviewer: { userId: 8, name: "Rae Kim" },
              reason: "Her mentor left midway",
            },
          }),
        ]),
      );
      decideMentorshipApproval.mockResolvedValue({ data: {} });
      await renderCard({ url: NEEDS_URL });

      expect(
        await screen.findByText("Waiting for approval — sent to Rae Kim"),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Withdraw" }),
      ).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Approve" }));
      const dialog = await screen.findByRole("dialog");
      expect(
        within(dialog).getByText(
          /Ann Lee goes into this round's matching pool/,
        ),
      ).toBeInTheDocument();
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Approve" }),
      );

      await waitFor(() =>
        expect(decideMentorshipApproval).toHaveBeenCalledWith(61, {
          decision: "approve",
          comment: undefined,
        }),
      );
    });
  });

  describe("Kit notifications", () => {
    const KIT_FLAG = { [FEATURE_FLAGS.MENTORSHIP_KIT_EMAIL]: true };

    const alice = participantRow({ userId: 11, pairs: [] });
    const cara = participantRow({
      userId: 12,
      firstName: "Cara",
      lastName: "Wang",
      preferredName: "Cara Wang",
      primaryEmail: "cara@x.com",
      participantRole: "mentee",
      pairs: [],
    });

    const pick = (name) =>
      userEvent.click(screen.getByRole("checkbox", { name: `Select ${name}` }));

    const sendButton = () =>
      screen.queryByRole("button", { name: /^Send notification · \d+$/ });

    beforeEach(() => {
      useFeatureFlags.mockReturnValue(KIT_FLAG);
      searchParticipants.mockResolvedValue(resultsOf([alice, cara]));
      listNotifiedStages.mockResolvedValue([
        { userId: 11, stages: ["round_recruitment", "admission"] },
      ]);
      listKitDrafts.mockResolvedValue([
        { id: 901, subject: "Your match", createdAt: "2026-10-02T00:00:00Z" },
      ]);
      createEmailSend.mockResolvedValue({
        sendId: 5,
        roundId: 7,
        stage: "admission",
        kitDraftId: 901,
        kitDraftSubject: "Your match",
        status: "draft",
      });
      refreshEmailPreview.mockResolvedValue({
        subject: "Your match",
        html: "<p>Hi</p>",
        senderAddress: "notification-test@circlecat.org",
        filterOk: true,
        recipientCount: 2,
        invalidHrefs: [],
        noEmail: [],
        recentlySentUserIds: [],
        previewToken: "tok",
      });
      confirmEmailSend.mockResolvedValue({ sendId: 5, status: "preparing" });
      cancelEmailSend.mockResolvedValue({ sendId: 5, status: "cancelled" });
      // vi.mock("sonner") does not reach the component's copy under Bazel.
      vi.spyOn(toast, "success").mockImplementation(() => {});
    });

    it("shows the stages each person was notified of this round", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      const cara = await screen.findByText("Cara Wang");

      expect(listNotifiedStages).toHaveBeenCalledWith("7");
      const aliceCell = cellOf(screen.getByText("Alice Doe"), "Notifications");
      await waitFor(() =>
        expect(aliceCell).toHaveTextContent(
          "New round invitationAdmission & onboarding",
        ),
      );
      expect(cellOf(cara, "Notifications")).toHaveTextContent(/^—$/);
    });

    it("shows no Notifications column and asks nothing with the flag off", async () => {
      useFeatureFlags.mockReturnValue({});
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Cara Wang");

      expect(
        screen.queryByRole("columnheader", { name: "Notifications" }),
      ).not.toBeInTheDocument();
      expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
      expect(listNotifiedStages).not.toHaveBeenCalled();
    });

    it("lets only mentorship admin writers pick people", async () => {
      useAuth.mockReturnValue({
        permissions: ["mentorship.admin.read"],
        user: { userId: 9 },
      });
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Cara Wang");

      expect(
        screen.getByRole("columnheader", { name: "Notifications" }),
      ).toBeInTheDocument();
      expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    });

    it("offers Send notification for the people picked", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Cara Wang");
      expect(sendButton()).not.toBeInTheDocument();

      await pick("Alice Doe");
      await pick("Cara Wang");

      expect(screen.getByText("2 people")).toBeInTheDocument();
      expect(sendButton()).toHaveTextContent("Send notification · 2");
      expect(
        screen.queryByRole("button", { name: /Send email/ }),
      ).not.toBeInTheDocument();
    });

    it("drops the picks when the list changes", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Cara Wang");
      await pick("Alice Doe");
      expect(sendButton()).toBeInTheDocument();

      await userEvent.type(screen.getByLabelText("Name / email"), "a");
      await search();
      await waitFor(() => expect(sendButton()).not.toBeInTheDocument());
    });

    it("keeps the Eligible for matching list to matching runs", async () => {
      useFeatureFlags.mockReturnValue({
        ...KIT_FLAG,
        [FEATURE_FLAGS.MATCHING_RUN]: true,
      });
      await renderCard({ url: "/?round=7&eligible=1" });
      await screen.findByText("Cara Wang");

      await pick("Alice Doe");

      expect(
        screen.getByRole("button", { name: "Run matching · 1" }),
      ).toBeInTheDocument();
      expect(sendButton()).not.toBeInTheDocument();
      expect(
        screen.queryByRole("columnheader", { name: "Notifications" }),
      ).not.toBeInTheDocument();
    });

    it("lets not registered people be picked, starting on New round invitation", async () => {
      searchUnregistered.mockResolvedValue({
        data: {
          rows: [
            {
              userId: 31,
              firstName: "Dana",
              lastName: "Wu",
              preferredName: "Dana Wu",
              primaryEmail: "dana@x.com",
              alternativeEmails: [],
              isBlocked: false,
              isDeactivated: false,
              isInternal: true,
              admittedRoles: ["mentee"],
              roundsTakenPart: 1,
              lastRoundName: "Spring 2026",
            },
          ],
          total: 1,
        },
      });
      listNotifiedStages.mockResolvedValue([
        { userId: 31, stages: ["round_recruitment"] },
      ]);
      await renderCard({ url: "/?round=7&notRegistered=1" });
      const dana = await screen.findByText("Dana Wu");
      await waitFor(() =>
        expect(cellOf(dana, "Notifications")).toHaveTextContent(
          "New round invitation",
        ),
      );

      await pick("Dana Wu");
      await userEvent.click(sendButton());

      const dialog = await screen.findByRole("dialog");
      expect(within(dialog).getByText("To 1 person")).toBeInTheDocument();
      expect(within(dialog).getByLabelText("Stage")).toHaveValue(
        "round_recruitment",
      );
    });

    it("schedules for the picked people, then clears the picks and reloads", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await screen.findByText("Cara Wang");
      await pick("Alice Doe");
      await pick("Cara Wang");
      await userEvent.click(sendButton());

      const dialog = await screen.findByRole("dialog");
      expect(
        within(dialog).getByText("Alice Doe, Cara Wang"),
      ).toBeInTheDocument();
      await within(dialog).findByRole("option", { name: "Your match" });
      await userEvent.selectOptions(
        within(dialog).getByLabelText("Stage"),
        "admission",
      );
      await userEvent.selectOptions(
        within(dialog).getByLabelText("Kit draft"),
        "901",
      );
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Create" }),
      );
      await within(dialog).findByTitle("Email preview");
      expect(createEmailSend).toHaveBeenCalledWith({
        roundId: 7,
        stage: "admission",
        kitDraftId: 901,
        userIds: [11, 12],
      });

      const date = within(dialog).getByLabelText("Send date");
      const time = within(dialog).getByLabelText("Send time");
      await userEvent.clear(date);
      await userEvent.type(date, "2030-10-20");
      await userEvent.clear(time);
      await userEvent.type(time, "09:00");
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Confirm" }),
      );

      await waitFor(() =>
        expect(toast.success).toHaveBeenCalledWith(
          "Scheduled for 2030-10-20 09:00 Pacific",
        ),
      );
      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );
      expect(sendButton()).not.toBeInTheDocument();
      expect(listNotifiedStages).toHaveBeenCalledTimes(2);
      expect(cancelEmailSend).not.toHaveBeenCalled();
    });
  });
});
