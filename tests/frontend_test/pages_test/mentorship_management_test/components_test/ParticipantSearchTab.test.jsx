import { render, screen, waitFor, within, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ParticipantSearchTab from "@/pages/MentorshipManagement/components/ParticipantSearchTab";
import { searchParticipants, getMeetingLog } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  searchParticipants: vi.fn(),
  getMeetingLog: vi.fn(),
}));

const TEST_ROUNDS = [
  { id: 1, name: "Spring 2026" },
  { id: 2, name: "Fall 2026" },
];

const renderTab = (participationStatus, rounds = TEST_ROUNDS) =>
  render(
    <ParticipantSearchTab
      participationStatus={participationStatus}
      rounds={rounds}
    />,
  );

const search = () =>
  userEvent.click(screen.getByRole("button", { name: "Search" }));

const participantRow = (overrides = {}) => ({
  userId: 1,
  firstName: "Alice",
  lastName: "Doe",
  preferredName: "Alice Doe",
  primaryEmail: "alice@x.com",
  alternativeEmails: [],
  roundName: "Spring 2026",
  participantRole: "mentor",
  approvalStatus: "matched",
  mentorOnboardingStatus: "done",
  menteeOnboardingStatus: null,
  matchedUser: {
    id: 2,
    firstName: "Bob",
    lastName: "Smith",
    preferredName: "Bob Smith",
  },
  completedMeetingCount: 2,
  requiredMeetings: 5,
  pairId: 80,
  ...overrides,
});

const nonParticipantRow = (overrides = {}) => ({
  userId: 1,
  firstName: "Alice",
  lastName: "Doe",
  preferredName: "Alice Doe",
  primaryEmail: "alice@x.com",
  alternativeEmails: [],
  mentorOnboardingStatus: "done",
  menteeOnboardingStatus: "in_progress",
  ...overrides,
});

describe("ParticipantSearchTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMeetingLog.mockResolvedValue({
      data: { roundVersion: "v2", meetings: [] },
    });
  });

  it("does not fetch on mount in participant mode", () => {
    renderTab("participant");
    expect(searchParticipants).not.toHaveBeenCalled();
  });

  it("does not fetch on mount in non-participant mode", () => {
    renderTab("non_participant");
    expect(searchParticipants).not.toHaveBeenCalled();
    expect(
      screen.getByText("Enter search criteria and click Search."),
    ).toBeInTheDocument();
  });

  it("renders all column headers after a search in participant mode", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");
    await search();
    await waitFor(() => expect(searchParticipants).toHaveBeenCalled());

    [
      "User ID",
      "First Name",
      "Last Name",
      "Preferred Name",
      "Primary Email",
      "Alternative Email(s)",
      "Round",
      "Role",
      "Approval Status",
      "Onboarding Status",
      "Matched User",
      "Meetings",
    ].forEach((col) => expect(screen.getByText(col)).toBeInTheDocument());
  });

  it("renders the base and onboarding column headers in non-participant mode", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [nonParticipantRow()], total: 1 },
    });
    renderTab("non_participant");
    await search();
    await waitFor(() => expect(searchParticipants).toHaveBeenCalled());

    [
      "User ID",
      "First Name",
      "Last Name",
      "Preferred Name",
      "Primary Email",
      "Alternative Email(s)",
      "Mentor Onboarding",
      "Mentee Onboarding",
    ].forEach((col) => expect(screen.getByText(col)).toBeInTheDocument());
    [
      "Round",
      "Role",
      "Approval Status",
      "Onboarding Status",
      "Matched User",
      "Meetings",
    ].forEach((col) => expect(screen.queryByText(col)).not.toBeInTheDocument());
  });

  it("searches participants and renders the results", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");

    await userEvent.type(screen.getByPlaceholderText("Name"), "Alice");
    await search();

    await waitFor(() =>
      expect(searchParticipants).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Alice",
          participationStatus: "participant",
        }),
      ),
    );
    expect(await screen.findByText("Spring 2026")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Doe")).toBeInTheDocument();
    expect(screen.getByText("Bob Smith")).toBeInTheDocument(); // matchedUser
    expect(screen.getByText("2/5")).toBeInTheDocument(); // completedMeetingCount / requiredMeetings
    expect(screen.getByText("alice@x.com")).toBeInTheDocument();
  });

  it("searches non-participants and renders the results", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [nonParticipantRow()], total: 1 },
    });
    renderTab("non_participant");

    await userEvent.type(screen.getByPlaceholderText("Name"), "Alice");
    await search();

    await waitFor(() =>
      expect(searchParticipants).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Alice",
          participationStatus: "non_participant",
        }),
      ),
    );
    const nameCell = await screen.findByText("Alice");
    const row = nameCell.closest("tr");
    expect(within(row).getByText("Doe")).toBeInTheDocument();
    expect(within(row).getByText("done")).toBeInTheDocument(); // mentorOnboardingStatus
    expect(within(row).getByText("in_progress")).toBeInTheDocument(); // menteeOnboardingStatus
  });

  it("sends the selected approval status filter in participant mode", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");

    await userEvent.click(screen.getByLabelText("Approval status"));
    await userEvent.click(screen.getByText("Matched"));
    await search();

    await waitFor(() =>
      expect(searchParticipants).toHaveBeenCalledWith(
        expect.objectContaining({ approvalStatus: "matched" }),
      ),
    );
  });

  it("sends the selected onboarding status filter in non-participant mode", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [nonParticipantRow()], total: 1 },
    });
    renderTab("non_participant");

    await userEvent.click(screen.getByLabelText("Onboarding status"));
    await userEvent.click(screen.getByText("Completed"));
    await search();

    await waitFor(() =>
      expect(searchParticipants).toHaveBeenCalledWith(
        expect.objectContaining({
          onboardingStatus: "completed",
          participationStatus: "non_participant",
        }),
      ),
    );
  });

  it("renders the participant-only Matched User Name / Round filters", () => {
    renderTab("participant");
    expect(
      screen.getByPlaceholderText("Matched User Name"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Round")).toBeInTheDocument();
  });

  it("does not render the participant-only filters in non-participant mode", () => {
    renderTab("non_participant");
    expect(
      screen.queryByPlaceholderText("Matched User Name"),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Round")).not.toBeInTheDocument();
  });

  it("lists the given rounds by name and sends the selected round's id", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");

    await userEvent.click(screen.getByLabelText("Round"));
    expect(screen.getByText("Spring 2026")).toBeInTheDocument();
    expect(screen.getByText("Fall 2026")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Fall 2026"));
    await search();

    await waitFor(() =>
      expect(searchParticipants).toHaveBeenCalledWith(
        expect.objectContaining({ roundId: "2" }),
      ),
    );
  });

  it("strips non-digits from the User ID field", async () => {
    renderTab("non_participant");
    const idInput = screen.getByPlaceholderText("User ID");
    await userEvent.type(idInput, "a1b2c3");
    expect(idInput).toHaveValue("123");
  });

  it("renders a dash for each missing field instead of the literal null", async () => {
    searchParticipants.mockResolvedValue({
      data: {
        participantRows: [
          nonParticipantRow({
            userId: 3,
            firstName: "Carol",
            lastName: null,
            preferredName: "Carol Jones",
            primaryEmail: null,
            alternativeEmails: ["carol1@x.com", "carol2@x.com"],
          }),
        ],
        total: 1,
      },
    });
    renderTab("non_participant");
    await search();

    expect(await screen.findByText("Carol")).toBeInTheDocument();
    expect(screen.getByText("Carol Jones")).toBeInTheDocument();
    expect(screen.getByText("carol1@x.com")).toBeInTheDocument();
    expect(screen.getByText("+1 more")).toBeInTheDocument();
    expect(screen.queryByText("carol2@x.com")).not.toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2); // missing lastName, primaryEmail
    expect(
      screen.queryByText("null", { exact: false }),
    ).not.toBeInTheDocument();
  });

  it("reveals the remaining alternative emails as plain text when '+N more' is clicked", async () => {
    searchParticipants.mockResolvedValue({
      data: {
        participantRows: [
          nonParticipantRow({
            alternativeEmails: ["carol1@x.com", "carol2@x.com", "carol3@x.com"],
          }),
        ],
        total: 1,
      },
    });
    renderTab("non_participant");
    await search();

    expect(await screen.findByText("carol1@x.com")).toBeInTheDocument();
    await userEvent.click(screen.getByText("+2 more"));

    expect(await screen.findByText("carol2@x.com")).toBeInTheDocument();
    expect(screen.getByText("carol3@x.com")).toBeInTheDocument();
  });

  it("keeps the table and pager mounted while a search is loading, instead of collapsing the panel", async () => {
    let resolveFetch;
    searchParticipants.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    renderTab("participant");
    await search();

    // While the request is still pending, the table shell and pager must
    // already be mounted rather than replaced by a loading placeholder —
    // that swap is what makes the surrounding card jump around.
    expect(screen.getByText("User ID")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prev" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();

    await act(async () => {
      resolveFetch({
        data: { participantRows: [participantRow()], total: 1 },
      });
    });
    expect(await screen.findByText("Spring 2026")).toBeInTheDocument();
  });

  it("clicking the User ID header sorts by user_id ascending, then descending on a second click", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");
    await search();
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByText("User ID"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "asc" }),
      ),
    );

    await userEvent.click(screen.getByText("User ID"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "desc" }),
      ),
    );
  });

  it("clicking the User ID header a third time clears the sort back to the default order", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");
    await search();
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByText("User ID"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "asc" }),
      ),
    );
    await userEvent.click(screen.getByText("User ID"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "desc" }),
      ),
    );

    await userEvent.click(screen.getByText("User ID"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: undefined }),
      ),
    );
  });

  it("clicking a non-sortable column header does not trigger a new fetch", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");
    await search();
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByText("First Name"));
    expect(searchParticipants).toHaveBeenCalledTimes(1);
  });

  it("renders the Meetings value as a clickable link and opens the dialog on click", async () => {
    searchParticipants.mockResolvedValue({
      data: { participantRows: [participantRow()], total: 1 },
    });
    renderTab("participant");
    await search();

    const link = await screen.findByRole("button", { name: "2/5" });
    expect(getMeetingLog).not.toHaveBeenCalled();

    await userEvent.click(link);

    expect(
      screen.getByText(
        "Meeting Log — Alice Doe (Mentor) with Bob Smith (Mentee) · Spring 2026",
      ),
    ).toBeInTheDocument();
    await waitFor(() => expect(getMeetingLog).toHaveBeenCalledWith(80));
  });

  it("renders a plain dash instead of a link when the participant has no pair", async () => {
    searchParticipants.mockResolvedValue({
      data: {
        participantRows: [
          participantRow({
            pairId: null,
            matchedUser: null,
            completedMeetingCount: null,
            requiredMeetings: null,
          }),
        ],
        total: 1,
      },
    });
    renderTab("participant");
    await search();

    await screen.findByText("Alice");
    expect(
      screen.queryByRole("button", { name: /^\d+\/\d+$/ }),
    ).not.toBeInTheDocument();
  });

  it("does not fetch the meeting log for every row just from rendering the table", async () => {
    searchParticipants.mockResolvedValue({
      data: {
        participantRows: [
          participantRow({ userId: 1 }),
          participantRow({ userId: 2, pairId: 81 }),
        ],
        total: 2,
      },
    });
    renderTab("participant");
    await search();

    await screen.findAllByRole("button", { name: "2/5" });
    expect(getMeetingLog).not.toHaveBeenCalled();
  });
});
