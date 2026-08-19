import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipInfoBanner from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";

vi.mock(
  "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog",
  () => ({
    default: vi.fn((props) => (
      <div data-testid={`mock-registration-dialog-${props.role}`}>
        Dialog Locked: {props.isLocked ? "Yes" : "No"} | Role: {props.role}
      </div>
    )),
  }),
);

vi.mock("@/pages/PersonalDashboard/components/MatchingResultDialog", () => ({
  default: vi.fn((props) => (
    <div data-testid="mock-matching-dialog">
      Round: {props.roundName} | Can View: {props.canViewMatch ? "Yes" : "No"} |
      Status: {props.matchData?.currentStatus || "N/A"}
    </div>
  )),
}));

const FUTURE = "2026-12-01T00:00:00Z";
const PAST = "2026-01-01T00:00:00Z";

describe("MentorshipInfoBanner", () => {
  const defaultProps = {
    registration: null,
    isRegistrationOpen: true,
    isFeedbackEnabled: false,
    registrationEntries: [{ role: "mentee", deadlineAt: FUTURE, isOpen: true }],
    registeredRole: null,
    onSaveRegistration: vi.fn(),
    loadRegistrationForRole: vi.fn(),
    pastPartners: [],
    isPartnersLoading: false,
    onLoadPastPartners: vi.fn(),
    matchResult: null,
    matchResultRoundName: "Spring 2026",
    canViewMatch: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the MatchingResultDialog only when the user is registered", () => {
    const { rerender } = render(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: false }}
      />,
    );

    expect(
      screen.queryByTestId("mock-matching-dialog"),
    ).not.toBeInTheDocument();

    rerender(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: true }}
        registeredRole="mentee"
      />,
    );

    expect(screen.getByTestId("mock-matching-dialog")).toBeInTheDocument();
  });

  it("offers one dialog per open role when the user has not registered", () => {
    render(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: false, roundName: "Spring" }}
        registrationEntries={[
          { role: "mentor", deadlineAt: FUTURE, isOpen: true },
          { role: "mentee", deadlineAt: FUTURE, isOpen: true },
        ]}
      />,
    );

    expect(
      screen.getByTestId("mock-registration-dialog-mentor"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("mock-registration-dialog-mentee"),
    ).toBeInTheDocument();
  });

  // A closed window offers an unregistered user nothing to fill in and
  // nothing to read back, so it offers no entry point at all.
  it("hides the entry for a role whose deadline has passed", () => {
    render(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: false, roundName: "Spring" }}
        registrationEntries={[
          { role: "mentor", deadlineAt: PAST, isOpen: false },
          { role: "mentee", deadlineAt: FUTURE, isOpen: true },
        ]}
      />,
    );

    expect(
      screen.queryByTestId("mock-registration-dialog-mentor"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("mock-registration-dialog-mentee"),
    ).toBeInTheDocument();
  });

  it("offers no registration entry when every window has closed", () => {
    render(
      <MentorshipInfoBanner
        {...defaultProps}
        isRegistrationOpen={false}
        registration={{ isRegistered: false, roundName: "Spring" }}
        registrationEntries={[
          { role: "mentor", deadlineAt: PAST, isOpen: false },
          { role: "mentee", deadlineAt: PAST, isOpen: false },
        ]}
      />,
    );

    expect(
      screen.queryByTestId("mock-registration-dialog-mentor"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-registration-dialog-mentee"),
    ).not.toBeInTheDocument();
  });

  it("shows a single entry once registered", () => {
    render(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: true, roundName: "Spring" }}
        registrationEntries={[
          { role: "mentee", deadlineAt: FUTURE, isOpen: true },
        ]}
        registeredRole="mentee"
      />,
    );

    expect(
      screen.getByTestId("mock-registration-dialog-mentee"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-registration-dialog-mentor"),
    ).not.toBeInTheDocument();
  });

  // The settled role stays readable after its window shuts -- that is the
  // one closed entry a registered user still gets.
  it("keeps the registered role's entry after its window closes", () => {
    render(
      <MentorshipInfoBanner
        {...defaultProps}
        isRegistrationOpen={false}
        registration={{ isRegistered: true, roundName: "Spring" }}
        registrationEntries={[
          { role: "mentee", deadlineAt: PAST, isOpen: false },
        ]}
        registeredRole="mentee"
      />,
    );

    expect(
      screen.getByTestId("mock-registration-dialog-mentee"),
    ).toHaveTextContent("Dialog Locked: Yes");
  });

  it("passes match data props correctly to MatchingResultDialog", () => {
    const mockMatchData = { currentStatus: "matched" };

    render(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: true }}
        registeredRole="mentee"
        matchResult={mockMatchData}
        matchResultRoundName="Test Round"
        canViewMatch={true}
      />,
    );

    const dialog = screen.getByTestId("mock-matching-dialog");
    expect(dialog).toHaveTextContent("Round: Test Round");
    expect(dialog).toHaveTextContent("Can View: Yes");
    expect(dialog).toHaveTextContent("Status: matched");
  });

  it("does not render when registration is closed, no registration exists, and feedback is disabled", () => {
    const { container } = render(
      <MentorshipInfoBanner
        {...defaultProps}
        isRegistrationOpen={false}
        registration={null}
        registrationEntries={[]}
        isFeedbackEnabled={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the component even when registration is closed if historical registration data exists", () => {
    render(
      <MentorshipInfoBanner
        {...defaultProps}
        isRegistrationOpen={false}
        registration={{ id: 1, isRegistered: true }}
        registrationEntries={[
          { role: "mentee", deadlineAt: PAST, isOpen: false },
        ]}
        registeredRole="mentee"
      />,
    );
    expect(
      screen.getByTestId("mock-registration-dialog-mentee"),
    ).toBeInTheDocument();
  });

  it("displays the goal section when a goal exists", () => {
    const registration = {
      roundPreferences: { goal: "Learn React Testing" },
    };
    render(
      <MentorshipInfoBanner {...defaultProps} registration={registration} />,
    );

    expect(screen.getByText("Current Mentorship Goal")).toBeInTheDocument();
    expect(screen.getByText("Learn React Testing")).toBeInTheDocument();
  });

  it("does not render the goal section when the goal is empty", () => {
    render(<MentorshipInfoBanner {...defaultProps} registration={null} />);
    expect(
      screen.queryByText("Current Mentorship Goal"),
    ).not.toBeInTheDocument();
  });

  it("locks the dialog of an entry whose own window has closed", () => {
    render(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: true }}
        registeredRole="mentor"
        registrationEntries={[
          { role: "mentor", deadlineAt: FUTURE, isOpen: true },
        ]}
      />,
    );
    expect(screen.getByText(/Dialog Locked: No/)).toBeInTheDocument();
  });

  it("does not offer feedback -- that lives on the participants card", () => {
    render(<MentorshipInfoBanner {...defaultProps} isFeedbackEnabled={true} />);

    expect(screen.queryByText(/Feedback/)).not.toBeInTheDocument();
  });
});
