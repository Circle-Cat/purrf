import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipInfoBanner from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";

vi.mock(
  "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog",
  () => ({
    default: vi.fn((props) => (
      <div data-testid="mock-registration-dialog">
        Dialog Locked: {props.isLocked ? "Yes" : "No"}
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

describe("MentorshipInfoBanner", () => {
  const defaultProps = {
    registration: null,
    isRegistrationOpen: true,
    isFeedbackEnabled: false,
    onSaveRegistration: vi.fn(),
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
      />,
    );

    expect(screen.getByTestId("mock-matching-dialog")).toBeInTheDocument();
  });

  it("passes match data props correctly to MatchingResultDialog", () => {
    const mockMatchData = { currentStatus: "matched" };

    render(
      <MentorshipInfoBanner
        {...defaultProps}
        registration={{ isRegistered: true }}
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
        registration={{ id: 1 }}
      />,
    );
    expect(screen.getByTestId("mock-registration-dialog")).toBeInTheDocument();
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

  it("passes isLocked correctly to the dialog based on isRegistrationOpen", () => {
    const { rerender } = render(
      <MentorshipInfoBanner {...defaultProps} isRegistrationOpen={true} />,
    );
    expect(screen.getByText("Dialog Locked: No")).toBeInTheDocument();

    rerender(
      <MentorshipInfoBanner
        {...defaultProps}
        isRegistrationOpen={false}
        registration={{}}
      />,
    );
    expect(screen.getByText("Dialog Locked: Yes")).toBeInTheDocument();
  });

  it("disables the feedback button and does not render it as a link when feedback is disabled", () => {
    render(
      <MentorshipInfoBanner {...defaultProps} isFeedbackEnabled={false} />,
    );

    const button = screen.getByRole("button", {
      name: /submit mentorship feedback/i,
    });
    expect(button).toBeDisabled();

    // Ensure no <a> element is rendered
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders a valid external link when feedback is enabled", () => {
    render(<MentorshipInfoBanner {...defaultProps} isFeedbackEnabled={true} />);

    const link = screen.getByRole("link", {
      name: /submit mentorship feedback/i,
    });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute(
      "href",
      "https://forms.google.com/mentorship-feedback",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    // The button should not be disabled in this case
    expect(link.closest("button") || link).not.toHaveAttribute("disabled");
  });
});
