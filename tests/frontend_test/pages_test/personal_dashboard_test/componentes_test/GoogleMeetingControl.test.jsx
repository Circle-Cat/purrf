import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { GoogleMeetingControl } from "@/pages/PersonalDashboard/components/GoogleMeetingControl";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import userEvent from "@testing-library/user-event";

vi.mock("@/hooks/useFeatureFlags", () => ({
  useFeatureFlags: vi.fn(),
}));

vi.mock("@/components/common/MeetingManagementDialog", () => ({
  default: ({ roundId }) => {
    const isDisabled = roundId === null || roundId === undefined;
    const tooltipText = isDisabled ? "No active mentorship round" : undefined;

    const handleButtonClick = () => {
      console.log("Current meetingRoundId:", roundId);
    };

    return (
      <div title={tooltipText}>
        <button disabled={isDisabled} onClick={handleButtonClick}>
          Manage Meetings
        </button>
      </div>
    );
  },
}));

describe("GoogleMeetingControl", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return null and render nothing when FEATURE_FLAGS.CREATE_GOOGLE_MEETING is false", () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: false,
    });

    const { container } = render(<GoogleMeetingControl meetingRoundId={123} />);

    expect(container.firstChild).toBeNull();
  });

  it("should disable the button and show tooltip warning when meetingRoundId is null", () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: true,
    });

    render(<GoogleMeetingControl meetingRoundId={null} />);

    const button = screen.getByRole("button", { name: /manage meetings/i });
    expect(button).toBeDisabled();

    const tooltipWrapper = screen.getByTitle("No active mentorship round");
    expect(tooltipWrapper).toContainElement(button);
  });

  it("should enable the button and remove tooltip when meetingRoundId is provided", () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: true,
    });

    render(<GoogleMeetingControl meetingRoundId={42} />);

    const button = screen.getByRole("button", { name: /manage meetings/i });
    expect(button).toBeEnabled();

    expect(
      screen.queryByTitle("No active mentorship round"),
    ).not.toBeInTheDocument();
  });

  it("should trigger click handler and log current meetingRoundId cleanly", async () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: true,
    });

    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});

    render(<GoogleMeetingControl meetingRoundId={99} />);

    const button = screen.getByRole("button", { name: /manage meetings/i });
    await userEvent.click(button);

    expect(consoleLogSpy).toHaveBeenCalledWith("Current meetingRoundId:", 99);

    consoleLogSpy.mockRestore();
  });
});
