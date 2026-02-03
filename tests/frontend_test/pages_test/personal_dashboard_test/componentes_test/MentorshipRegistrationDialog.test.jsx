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
    await user.type(textarea, longText);
    const expectedTest =
      "I want to learn React" +
      "A".repeat(300 - "I want to learn React".length);

    expect(textarea).toHaveValue(expectedTest);
    expect(screen.getByText("300 / 300")).toBeInTheDocument();
  });

  it("should call onSave with mapped data when Register is clicked", async () => {
    const mockPayload = { api: "data" };
    mapFormToApi.mockReturnValue(mockPayload);

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
});
