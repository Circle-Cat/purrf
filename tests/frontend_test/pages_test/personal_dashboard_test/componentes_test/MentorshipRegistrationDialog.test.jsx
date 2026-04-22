import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipRegistrationDialog from "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog";
import {
  mapRegistrationToForm,
  mapFormToApi,
} from "@/pages/PersonalDashboard/utils/mentorshipRegistration";

/**
 * Mock Dialog components.
 * This mock exposes a simple button to simulate opening/closing the dialog
 * via `onOpenChange`, instead of relying on Radix UI internals.
 */
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open, onOpenChange }) => (
    <div data-testid="dialog" data-open={open}>
      {children}
      {/* Simulate Dialog toggle behavior */}
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
 * Mock MultipleSelector component.
 * We keep only the minimal behavior required for testing:
 * - render an input for querying by placeholder
 * - expose disabled state
 * - simulate a simple selection action
 */
vi.mock("@/components/common/MultipleSelector", () => ({
  default: ({
    options,
    value,
    onChange,
    placeholder,
    disabled,
    maxSelected,
  }) => (
    <div
      data-testid={`selector-${placeholder}`}
      data-disabled={disabled}
      data-max-selected={maxSelected}
    >
      <input placeholder={placeholder} disabled={disabled} readOnly />

      <ul>
        {options?.map((opt) => (
          <li key={opt.id}>{opt.name}</li>
        ))}
      </ul>

      <div data-testid="selected-count">{value?.length || 0}</div>

      {!disabled && (
        <button
          onClick={() => {
            if (options?.length > 0) {
              onChange([...(value || []), options[0]]);
            }
          }}
        >
          Select First
        </button>
      )}
    </div>
  ),
}));

/**
 * Mock registration utility functions.
 * These are pure mapping helpers and should not be tested here.
 */
vi.mock("@/pages/PersonalDashboard/utils/mentorshipRegistration", () => ({
  INDUSTRY_CONFIG: [{ label: "Tech", value: "tech" }],
  SKILLSET_CONFIG: [{ label: "React", value: "react" }],
  CAREER_TRANSITION_OPTIONS: [
    { id: "none", label: "No career transition" },
    { id: "other", label: "Other (please briefly describe)" },
  ],
  REGION_OPTIONS: [
    { id: "us", label: "United States" },
    { id: "other", label: "Other (please specify)" },
  ],
  EXTERNAL_MENTORING_OPTIONS: [
    { id: "none", label: "No" },
    { id: "1_to_3", label: "1-3 mentoring relationships" },
  ],
  CURRENT_BACKGROUND_OPTIONS: [
    { id: "cs_grad", label: "CS undergrad or master's" },
    { id: "other", label: "Other (please briefly describe)" },
  ],
  CURRENT_STAGE_OPTIONS: [
    { id: "job_searching", label: "Looking for a job" },
    { id: "employed_growing", label: "Currently employed" },
  ],
  TIME_URGENCY_OPTIONS: [
    { id: "within_3_months", label: "Within 3 months" },
    { id: "1_year_plus", label: "1 year or more" },
  ],
  TARGET_REGION_OPTIONS: [
    { id: "us", label: "United States" },
    { id: "other", label: "Other (please specify)" },
  ],
  mapRegistrationToForm: vi.fn(),
  mapFormToApi: vi.fn(),
}));

describe("MentorshipRegistrationDialog Component", () => {
  let user;

  const defaultProps = {
    currentRegistration: {
      roundPreferences: { participantRole: "mentee" },
    },
    allPastPartners: [
      { id: "1", preferredName: "Alice" },
      { id: "2", preferredName: "Bob" },
    ],
    isPartnersLoading: false,
    loadPastPartners: vi.fn(),
    refreshRegistration: vi.fn(),
    isLocked: false,
    onSave: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Initialize a new userEvent instance for each test
    user = userEvent.setup();

    mapRegistrationToForm.mockReturnValue({
      industries: [],
      skillsets: [],
      partnerCapacity: 1,
      goal: "",
      selectedPartners: [],
      excludedPartners: [],
      careerTransition: "",
      careerTransitionOther: "",
      region: "",
      regionOther: "",
      externalMentoringExp: "",
      currentBackground: "",
      currentBackgroundOther: "",
      targetRegion: "",
      targetRegionOther: "",
      currentStage: "",
      timeUrgency: "",
    });
  });

  it("should render the trigger button with correct text", () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);
    expect(screen.getByText("Register for Next Round")).toBeInTheDocument();

    render(<MentorshipRegistrationDialog {...defaultProps} isLocked />);
    expect(screen.getByText("View Registration")).toBeInTheDocument();
  });

  it("should call loadPastPartners and refreshRegistration when opened", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));

    expect(defaultProps.refreshRegistration).toHaveBeenCalled();
    expect(defaultProps.loadPastPartners).toHaveBeenCalled();
  });

  it("should show Industry selector for Mentee but not for Mentor", async () => {
    const { rerender } = render(
      <MentorshipRegistrationDialog {...defaultProps} />,
    );

    await user.click(screen.getByText("Toggle Dialog"));
    expect(
      screen.queryByText(/Which industry are you interested in/i),
    ).toBeInTheDocument();

    // Switch role to Mentor and verify Industry selector is hidden
    rerender(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    expect(
      screen.queryByText(/Which industry are you interested in/i),
    ).not.toBeInTheDocument();
  });

  it("should show Capacity RadioGroup for Mentor", async () => {
    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(/How much time do you want to invest/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 mentee/i)).toBeInTheDocument();
    expect(screen.getByText(/3 mentees/i)).toBeInTheDocument();
  });

  it("should handle Goal text input changes and enforce 300 character limit", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));

    const textarea = screen.getByPlaceholderText(
      "What do you hope to achieve?",
    );
    await user.type(textarea, "I want to learn React");

    expect(textarea).toHaveValue("I want to learn React");

    const longText = "A".repeat(305);
    await user.clear(textarea);
    await user.paste(longText);

    expect(textarea).toHaveValue("A".repeat(300));
    expect(screen.getByText("300 / 300")).toBeInTheDocument();
  });

  it("should call onSave with mapped data when Register is clicked", async () => {
    const mockPayload = { api: "data" };
    mapFormToApi.mockReturnValue(mockPayload);
    mapRegistrationToForm.mockReturnValue({
      industries: [{ label: "Tech", value: "tech" }],
      skillsets: [{ label: "React", value: "react" }],
      partnerCapacity: 1,
      goal: "",
      selectedPartners: [],
      excludedPartners: [],
      careerTransition: "",
      careerTransitionOther: "",
      region: "",
      regionOther: "",
      externalMentoringExp: "",
      currentBackground: "cs_grad",
      currentBackgroundOther: "",
      targetRegion: "us",
      targetRegionOther: "",
      currentStage: "job_searching",
      timeUrgency: "within_3_months",
    });

    render(<MentorshipRegistrationDialog {...defaultProps} />);
    await user.click(screen.getByText("Toggle Dialog"));

    await user.click(screen.getByText("Register"));

    expect(mapFormToApi).toHaveBeenCalled();
    expect(defaultProps.onSave).toHaveBeenCalledWith(mockPayload);
  });

  it("should disable inputs when isLocked is true", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} isLocked />);

    await user.click(screen.getByText("Toggle Dialog"));

    const textarea = screen.getByPlaceholderText(
      "What do you hope to achieve?",
    );
    expect(textarea).toBeDisabled();

    const industrySelector = screen.getByPlaceholderText(
      "Select industries...",
    );
    expect(industrySelector).toBeDisabled();

    // Submit button should not be visible when locked
    expect(screen.queryByText("Submit")).not.toBeInTheDocument();
  });

  it("should update internal state when currentRegistration changes while open", async () => {
    const { rerender } = render(
      <MentorshipRegistrationDialog {...defaultProps} />,
    );

    await user.click(screen.getByText("Toggle Dialog"));

    mapRegistrationToForm.mockReturnValueOnce({
      goal: "New Goal",
      industries: [],
      skillsets: [],
      partnerCapacity: 1,
      selectedPartners: [],
      excludedPartners: [],
      careerTransition: "",
      careerTransitionOther: "",
      region: "",
      regionOther: "",
      externalMentoringExp: "",
      currentBackground: "",
      currentBackgroundOther: "",
      targetRegion: "",
      targetRegionOther: "",
      currentStage: "",
      timeUrgency: "",
    });

    rerender(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{ id: "new-id" }}
      />,
    );

    const textarea = screen.getByPlaceholderText(
      "What do you hope to achieve?",
    );
    expect(textarea).toHaveValue("New Goal");
  });

  it("should close the dialog when Close button is clicked", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Close"));

    expect(screen.getByTestId("dialog")).toHaveAttribute("data-open", "false");
  });

  it("should render mentor survey questions for mentor role", async () => {
    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(/Do you have experience transitioning/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Which region are you currently primarily based in/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Do you have experience mentoring others outside/i),
    ).toBeInTheDocument();
  });

  it("should not render mentor survey questions for mentee role", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.queryByText(/Do you have experience transitioning/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Which region are you currently primarily based in/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Do you have experience mentoring others outside/i),
    ).not.toBeInTheDocument();
  });

  it("should render mentee survey questions for mentee role", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByText(/best describes your current situation/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Which stage are you currently in/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/How urgent is your timeline/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Which job market region are you targeting/i),
    ).toBeInTheDocument();
  });

  it("should not render mentee survey questions for mentor role", async () => {
    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.queryByText(/best describes your current situation/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Which stage are you currently in/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/How urgent is your timeline/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Which job market region are you targeting/i),
    ).not.toBeInTheDocument();
  });

  it("should show careerTransitionOther input when careerTransition is 'other'", async () => {
    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.queryByPlaceholderText("Please briefly describe..."),
    ).not.toBeInTheDocument();

    await user.click(screen.getByText("Other (please briefly describe)"));

    expect(
      screen.getByPlaceholderText("Please briefly describe..."),
    ).toBeInTheDocument();
  });

  it("should show targetRegionOther input when targetRegion is 'other'", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.queryByPlaceholderText("Please specify..."),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("radio", { name: "Other (please specify)" }),
    );

    expect(
      screen.getByPlaceholderText("Please specify..."),
    ).toBeInTheDocument();
  });

  it("should pre-populate survey fields from mapRegistrationToForm", async () => {
    mapRegistrationToForm.mockReturnValue({
      industries: [],
      skillsets: [],
      partnerCapacity: 1,
      goal: "",
      selectedPartners: [],
      excludedPartners: [],
      careerTransition: "other",
      careerTransitionOther: "My unique path",
      region: "",
      regionOther: "",
      externalMentoringExp: "",
      currentBackground: "",
      currentBackgroundOther: "",
      targetRegion: "",
      targetRegionOther: "",
      currentStage: "",
      timeUrgency: "",
    });

    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));

    const otherInput = screen.getByPlaceholderText(
      "Please briefly describe...",
    );
    expect(otherInput).toHaveValue("My unique path");
  });

  it("should include survey fields when calling mapFormToApi on save", async () => {
    mapRegistrationToForm.mockReturnValue({
      industries: [],
      skillsets: [{ label: "React", value: "react" }],
      partnerCapacity: 1,
      goal: "",
      selectedPartners: [],
      excludedPartners: [],
      careerTransition: "none",
      careerTransitionOther: "",
      region: "us",
      regionOther: "",
      externalMentoringExp: "1_to_3",
      currentBackground: "",
      currentBackgroundOther: "",
      targetRegion: "",
      targetRegionOther: "",
      currentStage: "",
      timeUrgency: "",
    });

    const mockPayload = { api: "data" };
    mapFormToApi.mockReturnValue(mockPayload);

    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Register"));

    expect(mapFormToApi).toHaveBeenCalledWith(
      expect.objectContaining({
        careerTransition: "none",
        region: "us",
        externalMentoringExp: "1_to_3",
      }),
      expect.anything(),
    );
    expect(defaultProps.onSave).toHaveBeenCalledWith(mockPayload);
  });

  it("should block mentee submit and show errors when required fields are empty", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Register"));

    expect(defaultProps.onSave).not.toHaveBeenCalled();
    expect(mapFormToApi).not.toHaveBeenCalled();
    // 4 generic "This field is required." errors: background, stage, urgency,
    // targetRegion. industry and skillset have specific messages asserted below.
    expect(screen.getAllByText("This field is required.").length).toBe(4);
    expect(screen.getByText("Please select an industry.")).toBeInTheDocument();
    expect(
      screen.getByText("Please select at least one skillset."),
    ).toBeInTheDocument();
  });

  it("should block mentor submit and show errors when required fields are empty", async () => {
    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Register"));

    expect(defaultProps.onSave).not.toHaveBeenCalled();
    expect(mapFormToApi).not.toHaveBeenCalled();
    // One error per required mentor field: skillset, careerTransition,
    // region, externalMentoringExp.
    expect(screen.getAllByText("This field is required.").length).toBe(3);
    expect(
      screen.getByText("Please select at least one skillset."),
    ).toBeInTheDocument();
  });

  it("should block submit when 'Other' text is whitespace-only", async () => {
    mapRegistrationToForm.mockReturnValue({
      industries: [{ label: "Tech", value: "tech" }],
      skillsets: [{ label: "React", value: "react" }],
      partnerCapacity: 1,
      goal: "",
      selectedPartners: [],
      excludedPartners: [],
      careerTransition: "",
      careerTransitionOther: "",
      region: "",
      regionOther: "",
      externalMentoringExp: "",
      currentBackground: "other",
      currentBackgroundOther: "   ",
      targetRegion: "us",
      targetRegionOther: "",
      currentStage: "job_searching",
      timeUrgency: "within_3_months",
    });

    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Register"));

    expect(defaultProps.onSave).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please describe your current background."),
    ).toBeInTheDocument();
  });

  it("should block mentor submit when careerTransitionOther is whitespace-only", async () => {
    mapRegistrationToForm.mockReturnValue({
      industries: [],
      skillsets: [{ label: "React", value: "react" }],
      partnerCapacity: 1,
      goal: "",
      selectedPartners: [],
      excludedPartners: [],
      careerTransition: "other",
      careerTransitionOther: "   ",
      region: "us",
      regionOther: "",
      externalMentoringExp: "none",
      currentBackground: "",
      currentBackgroundOther: "",
      targetRegion: "",
      targetRegionOther: "",
      currentStage: "",
      timeUrgency: "",
    });

    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Register"));

    expect(defaultProps.onSave).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please describe your career transition background."),
    ).toBeInTheDocument();
  });

  it("should clear a field error when the user makes a valid selection", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} />);

    await user.click(screen.getByText("Toggle Dialog"));
    await user.click(screen.getByText("Register"));

    // 4 "This field is required." errors: currentBackground, currentStage, timeUrgency, targetRegion
    expect(screen.getAllByText("This field is required.").length).toBe(4);

    await user.click(screen.getByRole("radio", { name: "Looking for a job" }));

    // currentStage error cleared; remaining: currentBackground, timeUrgency, targetRegion
    expect(screen.getAllByText("This field is required.").length).toBe(3);
  });

  it("should disable survey radio questions when isLocked is true", async () => {
    render(<MentorshipRegistrationDialog {...defaultProps} isLocked />);

    await user.click(screen.getByText("Toggle Dialog"));

    expect(
      screen.getByRole("radio", { name: "CS undergrad or master's" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("radio", { name: "Looking for a job" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("radio", { name: "Within 3 months" }),
    ).toBeDisabled();
    expect(screen.getByRole("radio", { name: "United States" })).toBeDisabled();
  });

  it("should clear *Other text when user changes selection away from 'other'", async () => {
    render(
      <MentorshipRegistrationDialog
        {...defaultProps}
        currentRegistration={{
          roundPreferences: { participantRole: "mentor" },
        }}
      />,
    );

    await user.click(screen.getByText("Toggle Dialog"));

    // Select "Other" and type into the free-text input
    await user.click(
      screen.getByRole("radio", { name: "Other (please briefly describe)" }),
    );
    const otherInput = screen.getByPlaceholderText(
      "Please briefly describe...",
    );
    await user.type(otherInput, "Some explanation");
    expect(otherInput).toHaveValue("Some explanation");

    // Change to a non-other option — input disappears
    await user.click(
      screen.getByRole("radio", { name: "No career transition" }),
    );
    expect(
      screen.queryByPlaceholderText("Please briefly describe..."),
    ).not.toBeInTheDocument();

    // Re-select "Other" — input reappears empty (stale text was cleared)
    await user.click(
      screen.getByRole("radio", { name: "Other (please briefly describe)" }),
    );
    expect(
      screen.getByPlaceholderText("Please briefly describe..."),
    ).toHaveValue("");
  });
});
