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
  getMeetingLog,
  updateMeetingLog,
  getRoundFeedback,
  getAllMentorshipRounds,
} from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  searchParticipants: vi.fn(),
  getMeetingLog: vi.fn(),
  updateMeetingLog: vi.fn(),
  getRoundFeedback: vi.fn(),
  getAllMentorshipRounds: vi.fn(),
}));

// Latest first, as the API returns them; the latest has the higher id here so
// that picking the lowest id instead of the first would show.
const TEST_ROUNDS = [
  { id: 7, name: "Fall 2026" },
  { id: 3, name: "Spring 2026" },
];

let navigateTo;

const LocationProbe = () => {
  const location = useLocation();
  navigateTo = useNavigate();
  return <div data-testid="location-search">{location.search}</div>;
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
        participationStatus: "participant",
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
        participationStatus: "participant",
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
          participationStatus: "participant",
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
          participationStatus: "participant",
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

    it("lays out the filter bar in order, ending with Search", async () => {
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
      ]);
      expect(bar.lastElementChild).toBe(
        screen.getByRole("button", { name: "Search" }),
      );
    });

    it("sends participation_status participant on every search", async () => {
      await renderCard({ url: SEARCHED_PARTICIPANTS });
      await mounted();
      expect(searchParticipants.mock.calls[0][0].participationStatus).toBe(
        "participant",
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
      expect(within(cell).queryByRole("link")).not.toBeInTheDocument();
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
      expect(within(pair).getByText("with Bob Smith (22)")).toBeInTheDocument();
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
});
