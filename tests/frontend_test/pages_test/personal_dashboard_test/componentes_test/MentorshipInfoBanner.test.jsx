import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import MentorshipInfoBanner, {
  TRAINING_PATH,
} from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";
import MentorshipRegistrationDialog from "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog";

vi.mock(
  "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog",
  () => ({
    default: vi.fn((props) => (
      <button data-testid={`mock-registration-dialog-${props.role}`}>
        {props.isLocked ? "View" : "Open"} {props.role}
      </button>
    )),
  }),
);

vi.mock("@/pages/PersonalDashboard/components/MatchingResultDialog", () => ({
  default: vi.fn((props) => (
    <div data-testid="mock-matching-dialog">
      {props.roundName} | {props.matchData?.currentStatus}
    </div>
  )),
}));

const TZ = "America/New_York";

// Shaped like GET /mentorship/rounds entries.
const REG_ROUND = {
  id: 42,
  name: "2027 Spring",
  timeline: {
    promotionStartAt: "2026-12-18T08:00:00Z",
    onboardingDeadlineAt: "2027-01-20T03:00:00Z", // Jan 19 in New York
    matchNotificationAt: "2027-02-13T03:30:00Z", // Feb 12 in New York
  },
};
const NEXT_ROUND = {
  id: 44,
  name: "2027 Summer",
  timeline: { promotionStartAt: "2027-04-18T07:00:00Z" },
};

const OPEN_NOW = "2027-01-05T15:00:00Z";

const baseProps = {
  isLoading: false,
  regRoundId: REG_ROUND.id,
  regRoundName: REG_ROUND.name,
  registration: { isRegistered: false, roundName: REG_ROUND.name },
  isRegistrationOpen: true,
  registrationDeadlineAt: REG_ROUND.timeline.onboardingDeadlineAt,
  isTrainingDone: false,
  roundSelectionData: { sortedRounds: [NEXT_ROUND, REG_ROUND] },
  userTimezone: TZ,
  registrationEntries: [
    {
      role: "mentee",
      deadlineAt: REG_ROUND.timeline.onboardingDeadlineAt,
      isOpen: true,
    },
  ],
  registeredRole: null,
  onSaveRegistration: vi.fn(),
  loadRegistrationForRole: vi.fn(),
  pastPartners: [],
  isPartnersLoading: false,
  onLoadPastPartners: vi.fn(),
  refreshRegistration: vi.fn(),
  matchResult: null,
  matchResultRoundName: "2027 Spring Matches",
  canViewMatch: false,
};

const registeredMentor = {
  registration: {
    isRegistered: true,
    roundName: REG_ROUND.name,
    roundPreferences: {
      participantRole: "mentor",
      goal: "Grow as a technical lead",
    },
  },
  registeredRole: "mentor",
  registrationEntries: [
    {
      role: "mentor",
      deadlineAt: REG_ROUND.timeline.onboardingDeadlineAt,
      isOpen: true,
    },
  ],
};

const renderBanner = (overrides = {}) =>
  render(
    <MemoryRouter>
      <MentorshipInfoBanner {...baseProps} {...overrides} />
    </MemoryRouter>,
  );

const nextBox = () => screen.getByTestId("mentorship-banner-next");
const profileLine = () =>
  screen.queryByText(/check that your profile is up to date/);

describe("MentorshipInfoBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(OPEN_NOW));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing while its data is loading", () => {
    const { container } = renderBanner({ isLoading: true });

    expect(container).toBeEmptyDOMElement();
  });

  describe("no round open", () => {
    it("says when the next round opens, with no bar, action or profile line", () => {
      renderBanner({
        regRoundId: null,
        regRoundName: "",
        registration: null,
        isRegistrationOpen: false,
        registrationEntries: [],
      });

      expect(screen.getByText("Mentorship")).toBeInTheDocument();
      expect(nextBox()).toHaveTextContent(
        "Next: registration for 2027 Summer opens Apr 18. We'll email you when it does.",
      );
      expect(screen.queryByRole("list")).not.toBeInTheDocument();
      expect(within(nextBox()).queryByRole("button")).not.toBeInTheDocument();
      expect(profileLine()).not.toBeInTheDocument();
    });
  });

  describe("registration open, not registered", () => {
    it("puts the registration dialog in the Next line, once", () => {
      renderBanner();

      expect(screen.getByText("2027 Spring")).toBeInTheDocument();
      expect(nextBox()).toHaveTextContent("Next: register by Jan 19.");
      expect(
        within(nextBox()).getByTestId("mock-registration-dialog-mentee"),
      ).toBeInTheDocument();
      expect(
        screen.getAllByTestId("mock-registration-dialog-mentee"),
      ).toHaveLength(1);
      expect(profileLine()).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Update profile →" }),
      ).toHaveAttribute("href", "/profile");
    });

    it("offers one dialog per open role only", () => {
      renderBanner({
        registrationEntries: [
          { role: "mentor", deadlineAt: null, isOpen: false },
          {
            role: "mentee",
            deadlineAt: REG_ROUND.timeline.onboardingDeadlineAt,
            isOpen: true,
          },
        ],
      });

      expect(
        screen.queryByTestId("mock-registration-dialog-mentor"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByTestId("mock-registration-dialog-mentee"),
      ).toBeInTheDocument();
    });

    it("goes amber and counts the days when the deadline is near", () => {
      vi.setSystemTime(new Date("2027-01-18T12:00:00Z"));

      renderBanner();

      expect(nextBox()).toHaveAttribute("data-tone", "amber");
      expect(nextBox()).toHaveTextContent(
        "Next: register by Jan 19 (in 1 day).",
      );
      const [props] = MentorshipRegistrationDialog.mock.calls.at(-1);
      expect(props.triggerClassName).toMatch(/amber/);
    });

    it("marks Register as the current step for assistive tech", () => {
      renderBanner();

      const list = screen.getByRole("list", { name: "Mentorship progress" });
      const items = within(list).getAllByRole("listitem");
      expect(items[0]).toHaveAttribute("aria-current", "step");
      expect(items[1]).not.toHaveAttribute("aria-current");
    });

    it("shows the narrow-screen step line", () => {
      renderBanner();

      expect(screen.getByText("Register · step 1 of 3")).toBeInTheDocument();
    });
  });

  describe("registration closed, not registered", () => {
    it("shows Register missed, no action and no profile line", () => {
      vi.setSystemTime(new Date("2027-01-25T00:00:00Z"));

      renderBanner({
        isRegistrationOpen: false,
        registrationEntries: [
          {
            role: "mentee",
            deadlineAt: REG_ROUND.timeline.onboardingDeadlineAt,
            isOpen: false,
          },
        ],
      });

      expect(nextBox()).toHaveTextContent(
        "Registration for 2027 Spring has closed. You can register when the next round opens. We'll email you when it does.",
      );
      expect(nextBox()).toHaveAttribute("data-tone", "muted");
      expect(screen.getByText("(missed)")).toBeInTheDocument();
      expect(
        screen.queryByTestId("mock-registration-dialog-mentee"),
      ).not.toBeInTheDocument();
      expect(profileLine()).not.toBeInTheDocument();
    });
  });

  describe("registered, training not done", () => {
    it("links to the training section and keeps Update registration in the header", () => {
      renderBanner(registeredMentor);

      expect(nextBox()).toHaveTextContent(
        "Next: finish your onboarding training by Jan 19.",
      );
      expect(
        within(nextBox()).getByRole("link", { name: "Go to training" }),
      ).toHaveAttribute("href", TRAINING_PATH);
      expect(TRAINING_PATH).toBe("/profile#training");
      const dialog = screen.getByTestId("mock-registration-dialog-mentor");
      expect(nextBox()).not.toContainElement(dialog);
      expect(screen.getByText("Grow as a technical lead")).toBeInTheDocument();
      expect(screen.getByText("Training · step 2 of 3")).toBeInTheDocument();
      expect(profileLine()).toBeInTheDocument();
    });

    it("leads with Overdue once the deadline has passed", () => {
      vi.setSystemTime(new Date("2027-01-25T00:00:00Z"));

      renderBanner({
        ...registeredMentor,
        isRegistrationOpen: false,
        registrationEntries: [
          {
            role: "mentor",
            deadlineAt: REG_ROUND.timeline.onboardingDeadlineAt,
            isOpen: false,
          },
        ],
      });

      expect(nextBox()).toHaveTextContent(
        "Overdue: your onboarding training was due Jan 19. Finish it before matches are made on Feb 12, or you can't be matched this round.",
      );
      expect(
        within(nextBox()).getByRole("link", { name: "Go to training" }),
      ).toBeInTheDocument();
      expect(screen.getByText("View mentor")).toBeInTheDocument();
    });
  });

  describe("registered and trained", () => {
    it("names the announcement date with no action", () => {
      renderBanner({ ...registeredMentor, isTrainingDone: true });

      expect(nextBox()).toHaveTextContent(
        "Next: matches are announced Feb 12.",
      );
      expect(within(nextBox()).queryByRole("link")).not.toBeInTheDocument();
      expect(screen.getAllByText("(done)")).toHaveLength(2);
      expect(profileLine()).toBeInTheDocument();
    });
  });

  describe("matches announced", () => {
    const announced = {
      ...registeredMentor,
      isTrainingDone: true,
      isRegistrationOpen: false,
      canViewMatch: true,
    };

    beforeEach(() => {
      vi.setSystemTime(new Date("2027-02-14T00:00:00Z"));
    });

    it("offers the matching result to a matched viewer, with no bar", () => {
      renderBanner({
        ...announced,
        matchResult: { currentStatus: "matched", partners: [] },
      });

      expect(nextBox()).toHaveTextContent(
        "Next: see who you're matched with. Your meetings for this round are in Mentorship Participation below.",
      );
      expect(
        within(nextBox()).getByTestId("mock-matching-dialog"),
      ).toHaveTextContent("2027 Spring Matches | matched");
      expect(screen.queryByRole("list")).not.toBeInTheDocument();
      expect(screen.queryByText(/step \d of 3/)).not.toBeInTheDocument();
      expect(profileLine()).not.toBeInTheDocument();
    });

    it("tells an unmatched viewer, with no action", () => {
      renderBanner({
        ...announced,
        matchResult: { currentStatus: "unmatched", partners: [] },
      });

      expect(nextBox()).toHaveTextContent(
        "You weren't matched this round. You may still be matched with someone this round if a partner is available. You can register again when the next round opens.",
      );
      expect(
        screen.queryByTestId("mock-matching-dialog"),
      ).not.toBeInTheDocument();
      expect(profileLine()).not.toBeInTheDocument();
    });

    it("drops the result link and the registration entry for a withdrawn viewer", () => {
      renderBanner({
        ...announced,
        matchResult: {
          currentStatus: "withdrawn",
          partners: [{ id: 7, isActive: false }],
        },
      });

      expect(nextBox()).toHaveTextContent(
        "You've withdrawn from 2027 Spring. You can register again when the next round opens.",
      );
      expect(
        screen.queryByTestId("mock-matching-dialog"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("mock-registration-dialog-mentor"),
      ).not.toBeInTheDocument();
    });

    it("keeps the registration entry but not the result link once a pairing ended", () => {
      renderBanner({
        ...announced,
        matchResult: {
          currentStatus: "matched",
          partners: [{ id: 7, isActive: false }],
        },
      });

      expect(nextBox()).toHaveTextContent(
        "Your pairing for 2027 Spring has ended.",
      );
      expect(
        screen.queryByTestId("mock-matching-dialog"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByTestId("mock-registration-dialog-mentor"),
      ).toBeInTheDocument();
    });
  });

  describe("rejected before matches are announced", () => {
    it("says they are not taking part, with no training link, profile line or registration entry", () => {
      renderBanner({
        ...registeredMentor,
        matchResult: { currentStatus: "rejected", partners: [] },
      });

      expect(nextBox()).toHaveTextContent(
        "You aren't taking part in 2027 Spring. You can register again when the next round opens.",
      );
      expect(within(nextBox()).queryByRole("link")).not.toBeInTheDocument();
      expect(profileLine()).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("mock-registration-dialog-mentor"),
      ).not.toBeInTheDocument();
    });
  });
});
