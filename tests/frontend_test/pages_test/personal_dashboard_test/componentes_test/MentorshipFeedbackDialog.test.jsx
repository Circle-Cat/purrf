import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipFeedbackDialog from "@/pages/PersonalDashboard/components/MentorshipFeedbackDialog";
import {
  getMyMentorshipFeedback,
  postMyMentorshipFeedback,
} from "@/api/mentorshipApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { toast } from "sonner";

vi.mock("@/api/mentorshipApi", () => ({
  getMyMentorshipFeedback: vi.fn(),
  postMyMentorshipFeedback: vi.fn(),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

vi.mock("@/hooks/useFeatureFlags", () => ({
  useFeatureFlags: vi.fn(() => ({})),
}));

vi.mock("@/constants/FeatureFlags", () => ({
  FEATURE_FLAGS: { CREATE_GOOGLE_MEETING: "create-google-meeting" },
}));

/**
 * Radix Dialog does not render portal content in jsdom without this mock.
 * We expose a Toggle button to drive open/close in tests.
 */
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open, onOpenChange }) => (
    <div data-testid="dialog" data-open={String(open)}>
      {children}
      <button onClick={() => onOpenChange?.(!open)}>Toggle Dialog</button>
    </div>
  ),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogTrigger: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

/**
 * Radix Select does not render options in jsdom. We expose a native <select>
 * so tests can change values with userEvent.selectOptions.
 */
vi.mock("@/components/ui/select", () => ({
  Select: ({ value, onValueChange, children }) => (
    <select
      data-testid="sessions-select"
      value={value}
      onChange={(e) => onValueChange?.(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: () => null,
  SelectValue: () => null,
  SelectContent: ({ children }) => <>{children}</>,
  SelectItem: ({ value, children }) => (
    <option value={value}>{children}</option>
  ),
}));

/**
 * RadioGroup passes onValueChange via React context so RadioGroupItem can call
 * it when clicked — the Radix primitive does this internally but jsdom won't
 * execute the Radix event handling, so we replicate it here.
 */
vi.mock("@/components/ui/radio-group", async () => {
  const { createContext, useContext, createElement } = await import("react");
  const RadioCtx = createContext(null);
  return {
    RadioGroup: ({ value, onValueChange, children }) =>
      createElement(
        RadioCtx.Provider,
        { value: onValueChange },
        createElement(
          "div",
          { role: "radiogroup", "data-value": value },
          children,
        ),
      ),
    RadioGroupItem: ({ value, id }) => {
      const onChange = useContext(RadioCtx);
      return createElement("input", {
        type: "radio",
        id,
        value,
        onChange: () => onChange?.(value),
      });
    },
  };
});

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, className }) => (
    <button onClick={onClick} disabled={disabled} className={className}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/label", () => ({
  Label: ({ children, htmlFor, className }) => (
    <label htmlFor={htmlFor} className={className}>
      {children}
    </label>
  ),
}));

const menteeResponse = {
  participantRole: "mentee",
  hasSubmitted: false,
};

const mentorResponse = {
  participantRole: "mentor",
  hasSubmitted: false,
};

const submittedMenteeResponse = {
  participantRole: "mentee",
  hasSubmitted: true,
  sessionsCompleted: 3,
  mostValuableAspects: "Great sessions",
  challenges: "Scheduling",
  programRating: 4,
};

const defaultProps = {
  roundId: "round-1",
  roundName: "Spring 2025",
  isFeedbackEnabled: true,
};

describe("MentorshipFeedbackDialog", () => {
  let user;

  beforeEach(() => {
    vi.clearAllMocks();
    user = userEvent.setup();
    getMyMentorshipFeedback.mockResolvedValue({ data: menteeResponse });
    postMyMentorshipFeedback.mockResolvedValue({});
    useFeatureFlags.mockReturnValue({});
  });

  it("renders nothing until the initial status fetch resolves", () => {
    getMyMentorshipFeedback.mockReturnValue(new Promise(() => {}));
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders a disabled trigger button and logs the error when the initial fetch fails", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    getMyMentorshipFeedback.mockRejectedValue(new Error("boom"));
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() =>
      expect(screen.getByText("Submit Feedback")).toBeInTheDocument(),
    );
    expect(screen.getByText("Submit Feedback")).toBeDisabled();
    expect(errorSpy).toHaveBeenCalledWith(
      expect.stringContaining("failed to fetch feedback status"),
      expect.any(Error),
    );
    errorSpy.mockRestore();
  });

  it("shows 'Submit Feedback' when user has not submitted", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() =>
      expect(screen.getByText("Submit Feedback")).toBeInTheDocument(),
    );
  });

  it("shows 'View Feedback' when user has already submitted", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: { ...menteeResponse, hasSubmitted: true },
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() =>
      expect(screen.getByText("View Feedback")).toBeInTheDocument(),
    );
  });

  it("disables the trigger button and skips the fetch when isFeedbackEnabled is false", async () => {
    render(
      <MentorshipFeedbackDialog {...defaultProps} isFeedbackEnabled={false} />,
    );
    await waitFor(() => screen.getByText("Submit Feedback"));
    expect(screen.getByText("Submit Feedback")).toBeDisabled();
    expect(getMyMentorshipFeedback).not.toHaveBeenCalled();
  });

  it("renders a disabled button without fetching when roundId is null", async () => {
    render(
      <MentorshipFeedbackDialog
        {...defaultProps}
        roundId={null}
        isFeedbackEnabled={false}
      />,
    );
    await waitFor(() => screen.getByText("Submit Feedback"));
    expect(screen.getByText("Submit Feedback")).toBeDisabled();
    expect(getMyMentorshipFeedback).not.toHaveBeenCalled();
  });

  it("fetches feedback exactly once on mount", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Toggle Dialog"));
    expect(getMyMentorshipFeedback).toHaveBeenCalledTimes(1);
  });

  it("populates form fields when user has previously submitted", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("View Feedback"));

    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.getByTestId("sessions-select")).toHaveValue("3");
    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toHaveValue("Great sessions");
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toHaveValue("Scheduling");
  });

  it("shows sessions field only for mentee, free-text fields for all roles", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.getByTestId("sessions-select")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toBeInTheDocument();
  });

  it("hides sessions field for mentor role but shows free-text fields", async () => {
    getMyMentorshipFeedback.mockResolvedValue({ data: mentorResponse });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.queryByTestId("sessions-select")).not.toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toBeInTheDocument();
  });

  it("hides sessions field for mentee when create-google-meeting flag is on", async () => {
    useFeatureFlags.mockReturnValue({ "create-google-meeting": true });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.queryByTestId("sessions-select")).not.toBeInTheDocument();
  });

  it("shows inline errors for all empty required fields on submit (mentee)", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.click(screen.getByText("Submit"));

    const errors = screen.getAllByText("This field is required.");
    // sessionsCompleted + programRating = 2
    expect(errors.length).toBe(2);
    expect(postMyMentorshipFeedback).not.toHaveBeenCalled();
  });

  it("shows only programRating error for mentor (no sessions field)", async () => {
    getMyMentorshipFeedback.mockResolvedValue({ data: mentorResponse });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.click(screen.getByText("Submit"));

    const errors = screen.getAllByText("This field is required.");
    expect(errors.length).toBe(1);
  });

  it("posts feedback, closes the dialog, and shows a success toast on Submit", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.selectOptions(screen.getByTestId("sessions-select"), "3");
    await user.click(screen.getByLabelText("4"));

    await user.click(screen.getByText("Submit"));

    await waitFor(() => expect(toast.success).toHaveBeenCalled());

    expect(postMyMentorshipFeedback).toHaveBeenCalledWith("round-1", {
      sessionsCompleted: 3,
      mostValuableAspects: null,
      challenges: null,
      programRating: 4,
    });
    expect(screen.getByTestId("dialog")).toHaveAttribute("data-open", "false");
    expect(toast.success).toHaveBeenCalledWith(
      "Feedback Submitted",
      expect.objectContaining({
        description: expect.stringContaining("Spring 2025"),
      }),
    );
  });

  it("propagates text-area content through the POST payload", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.selectOptions(screen.getByTestId("sessions-select"), "2");
    await user.click(screen.getByLabelText("5"));
    await user.type(
      screen.getByPlaceholderText("Share what you found most valuable..."),
      "Hands-on pairing",
    );
    await user.type(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
      "Timezone gaps",
    );

    await user.click(screen.getByText("Submit"));

    await waitFor(() => expect(postMyMentorshipFeedback).toHaveBeenCalled());
    expect(postMyMentorshipFeedback).toHaveBeenCalledWith("round-1", {
      sessionsCompleted: 2,
      mostValuableAspects: "Hands-on pairing",
      challenges: "Timezone gaps",
      programRating: 5,
    });
  });

  it("shows an error toast, keeps the dialog open, and leaves hasSubmitted=false when POST fails", async () => {
    postMyMentorshipFeedback.mockRejectedValue(new Error("boom"));
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.selectOptions(screen.getByTestId("sessions-select"), "3");
    await user.click(screen.getByLabelText("4"));

    await user.click(screen.getByText("Submit"));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(toast.error).toHaveBeenCalledWith(
      "Submission Failed",
      expect.any(Object),
    );
    // Dialog stays open so the user can retry
    expect(screen.getByTestId("dialog")).toHaveAttribute("data-open", "true");
    // Button still reads "Submit Feedback" because hasSubmitted was not flipped
    expect(screen.getByText("Submit Feedback")).toBeInTheDocument();
  });

  it("shows read-only form with no submit button when user has already submitted", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("View Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.queryByText("Submit")).not.toBeInTheDocument();
    expect(screen.queryByText("Update")).not.toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toBeDisabled();
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toBeDisabled();
  });

  it("closes dialog when Close button is clicked", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.click(screen.getByText("Close"));

    expect(screen.getByTestId("dialog")).toHaveAttribute("data-open", "false");
  });

  it("resets unsubmitted form fields when the dialog is closed", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.type(
      screen.getByPlaceholderText("Share what you found most valuable..."),
      "Some text",
    );

    await user.click(screen.getByText("Close"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toHaveValue("");
  });

  it("hides submit button in footer when user has already submitted", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("View Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.queryByText("Submit")).not.toBeInTheDocument();
    expect(screen.queryByText("Update")).not.toBeInTheDocument();
    expect(screen.getByText("Close")).toBeInTheDocument();
  });
});
