import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipFeedbackDialog from "@/pages/PersonalDashboard/components/MentorshipFeedbackDialog";
import {
  getMyMentorshipFeedback,
  getMyMentorshipPartners,
  postMyMentorshipFeedback,
} from "@/api/mentorshipApi";
import { toast } from "sonner";

vi.mock("@/api/mentorshipApi", () => ({
  getMyMentorshipFeedback: vi.fn(),
  getMyMentorshipPartners: vi.fn(),
  postMyMentorshipFeedback: vi.fn(),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

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
  mostValuableAspects: "Great sessions",
  challenges: "Scheduling",
  programRating: 4,
};

const defaultProps = {
  roundId: "round-1",
  roundName: "Spring 2025",
  isEditable: true,
  feedbackDeadlineText: "May 9, 2026 23:59 Asia/Shanghai",
};

const multiplePartners = [
  {
    id: 20,
    firstName: "Robert",
    lastName: "Smith",
    preferredName: "Bob Smith",
  },
  {
    id: 21,
    firstName: "Jennifer",
    lastName: "Martinez",
    preferredName: "Jennifer Martinez",
  },
];

describe("MentorshipFeedbackDialog", () => {
  let user;

  beforeEach(() => {
    vi.clearAllMocks();
    user = userEvent.setup();
    getMyMentorshipFeedback.mockResolvedValue({ data: menteeResponse });
    getMyMentorshipPartners.mockResolvedValue({ data: [] });
    postMyMentorshipFeedback.mockResolvedValue({});
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

  it("shows 'Edit Feedback' when user has already submitted and the window is open", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: { ...menteeResponse, hasSubmitted: true },
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() =>
      expect(screen.getByText("Edit Feedback")).toBeInTheDocument(),
    );
  });

  it("shows 'View Feedback' once the deadline has passed", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: { ...menteeResponse, hasSubmitted: true },
    });
    render(<MentorshipFeedbackDialog {...defaultProps} isEditable={false} />);
    await waitFor(() =>
      expect(screen.getByText("View Feedback")).toBeInTheDocument(),
    );
  });

  it("renders nothing after the deadline when nothing was submitted", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} isEditable={false} />);
    await waitFor(() => expect(getMyMentorshipFeedback).toHaveBeenCalled());
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders a disabled button without fetching when roundId is null", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} roundId={null} />);
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
    await waitFor(() => screen.getByText("Edit Feedback"));

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toHaveValue("Great sessions");
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toHaveValue("Scheduling");
  });

  it("no longer asks how many sessions were completed", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.queryByText(/How many sessions/)).not.toBeInTheDocument();
  });

  it("shows the free-text fields for a mentee", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toBeInTheDocument();
  });

  it("shows the same free-text fields for a mentor", async () => {
    getMyMentorshipFeedback.mockResolvedValue({ data: mentorResponse });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toBeInTheDocument();
  });

  it("shows an inline error for the empty required field on submit (mentee)", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.click(screen.getByText("Submit"));

    const errors = screen.getAllByText("This field is required.");
    // programRating is the only always-required field
    expect(errors.length).toBe(1);
    expect(postMyMentorshipFeedback).not.toHaveBeenCalled();
  });

  it("shows the same programRating error for a mentor", async () => {
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

    await user.click(screen.getByLabelText("4"));

    await user.click(screen.getByText("Submit"));

    await waitFor(() => expect(toast.success).toHaveBeenCalled());

    expect(postMyMentorshipFeedback).toHaveBeenCalledWith("round-1", {
      mostValuableAspects: null,
      challenges: null,
      programRating: 4,
      partnerFeedback: [],
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
      mostValuableAspects: "Hands-on pairing",
      challenges: "Timezone gaps",
      programRating: 5,
      partnerFeedback: [],
    });
  });

  it("shows an error toast, keeps the dialog open, and leaves hasSubmitted=false when POST fails", async () => {
    postMyMentorshipFeedback.mockRejectedValue(new Error("boom"));
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

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

  it("shows a read-only form with no submit button once the deadline has passed", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} isEditable={false} />);
    await waitFor(() => screen.getByText("View Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.queryByText("Submit")).not.toBeInTheDocument();
    expect(screen.queryByText("Save Changes")).not.toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).toBeDisabled();
    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toBeDisabled();
  });

  it("keeps a submitted form editable while the window is open", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Edit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByPlaceholderText("Share what you found most valuable..."),
    ).not.toBeDisabled();
    expect(screen.getByText("Save Changes")).toBeInTheDocument();
  });

  it("posts the edited answers and reports an update when re-submitting", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Edit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    const challenges = screen.getByPlaceholderText(
      "Describe any challenges you faced...",
    );
    await user.clear(challenges);
    await user.type(challenges, "Nothing this time");

    await user.click(screen.getByText("Save Changes"));

    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(postMyMentorshipFeedback).toHaveBeenCalledWith(
      "round-1",
      expect.objectContaining({ challenges: "Nothing this time" }),
    );
    expect(toast.success).toHaveBeenCalledWith(
      "Feedback Updated",
      expect.any(Object),
    );
  });

  it("discards unsaved edits to submitted feedback when the dialog is closed", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Edit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    const challenges = screen.getByPlaceholderText(
      "Describe any challenges you faced...",
    );
    await user.clear(challenges);
    await user.type(challenges, "Typed but never saved");

    await user.click(screen.getByText("Close"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByPlaceholderText("Describe any challenges you faced..."),
    ).toHaveValue("Scheduling");
  });

  it("shows the deadline in the editable hint", async () => {
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(
        /You can update your responses until May 9, 2026 23:59 Asia\/Shanghai\./,
      ),
    ).toBeInTheDocument();
  });

  it("falls back to generic wording when no deadline is known", async () => {
    render(
      <MentorshipFeedbackDialog
        {...defaultProps}
        feedbackDeadlineText={null}
      />,
    );
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(
        /You can update your responses until the feedback deadline\./,
      ),
    ).toBeInTheDocument();
  });

  it("says the deadline has passed in read-only mode", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} isEditable={false} />);
    await waitFor(() => screen.getByText("View Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(
        /The feedback deadline passed on May 9, 2026 23:59 Asia\/Shanghai\. Your responses are read-only\./,
      ),
    ).toBeInTheDocument();
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

  it("hides submit button in footer once the deadline has passed", async () => {
    getMyMentorshipFeedback.mockResolvedValue({
      data: submittedMenteeResponse,
    });
    render(<MentorshipFeedbackDialog {...defaultProps} isEditable={false} />);
    await waitFor(() => screen.getByText("View Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(screen.queryByText("Submit")).not.toBeInTheDocument();
    expect(screen.queryByText("Save Changes")).not.toBeInTheDocument();
    expect(screen.getByText("Close")).toBeInTheDocument();
  });

  it("renders a rating and feedback question for each partner", async () => {
    getMyMentorshipPartners.mockResolvedValue({ data: multiplePartners });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(
        /How was your overall experience working with your mentor Bob Smith\?/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Share feedback about Bob Smith..."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /How was your overall experience working with your mentor Jennifer Martinez\?/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Share feedback about Jennifer Martinez..."),
    ).toBeInTheDocument();
  });

  it("names a partner by their full name when they have no preferred name", async () => {
    getMyMentorshipPartners.mockResolvedValue({
      data: [
        { id: 22, firstName: "Robert", lastName: "Smith", preferredName: null },
      ],
    });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(
        /How was your overall experience working with your mentor Robert Smith\?/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /What feedback would you like to share about your mentor Robert Smith\?/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Share feedback about Robert Smith..."),
    ).toBeInTheDocument();
  });

  it("requires a rating for every partner before submitting", async () => {
    getMyMentorshipPartners.mockResolvedValue({ data: multiplePartners });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    // Satisfy the unrelated required fields so the only errors left after
    // submit are the partner ratings this test cares about.
    await user.click(screen.getByLabelText("4"));

    await user.click(screen.getByText("Submit"));

    expect(screen.getAllByText("This field is required.").length).toBe(
      multiplePartners.length,
    );
    expect(postMyMentorshipFeedback).not.toHaveBeenCalled();
  });

  it("submits a rating and feedback entry per partner", async () => {
    getMyMentorshipPartners.mockResolvedValue({ data: multiplePartners });
    render(<MentorshipFeedbackDialog {...defaultProps} />);
    await waitFor(() => screen.getByText("Submit Feedback"));
    await user.click(screen.getByText("Toggle Dialog"));

    await user.click(screen.getByLabelText("4"));

    const excellentOptions = screen.getAllByLabelText("Excellent");
    const poorOptions = screen.getAllByLabelText("Poor");
    await user.click(excellentOptions[0]); // Bob Smith
    await user.click(poorOptions[1]); // Jennifer Martinez

    await user.type(
      screen.getByPlaceholderText("Share feedback about Bob Smith..."),
      "Very supportive",
    );

    await user.click(screen.getByText("Submit"));

    await waitFor(() => expect(postMyMentorshipFeedback).toHaveBeenCalled());
    expect(postMyMentorshipFeedback).toHaveBeenCalledWith("round-1", {
      mostValuableAspects: null,
      challenges: null,
      programRating: 4,
      partnerFeedback: [
        { partnerId: 20, rating: 5, feedback: "Very supportive" },
        { partnerId: 21, rating: 1, feedback: null },
      ],
    });
  });
});
