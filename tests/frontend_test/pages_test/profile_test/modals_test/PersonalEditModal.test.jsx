import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import PersonalEditModal from "@/pages/Profile/modals/PersonalEditModal";
import { useAuth } from "@/context/auth/AuthContext";
import { USER_ROLES } from "@/constants/UserRoles";

vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/pages/Profile/utils", () => ({
  TimezoneEnum: {
    UTC: "UTC",
    EST: "EST",
  },
  formatTimezoneLabel: (tz) => `Formatted ${tz}`,
  CommunicationMethodEnum: {
    Email: "Email",
    GoogleChat: "GoogleChat",
  },
  isValidEmail: (email) => email.includes("@"),
}));

vi.mock("@/pages/Profile/modals/Modal.css", () => ({}));

describe("PersonalEditModal Component", () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();

  const initialData = {
    firstName: "John",
    lastName: "Doe",
    preferredName: "Johnny",
    timezone: "UTC",
    linkedin: "linkedin.com/in/johndoe",
    communicationMethod: "Email",
    emails: [
      { id: "1", email: "primary@example.com", isPrimary: true },
      { id: "2", email: "alt@example.com", isPrimary: false },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();

    useAuth.mockReturnValue({
      roles: [USER_ROLES.CONTACT_GOOGLE_CHAT],
      loading: false,
    });
  });

  it("should not render when isOpen is false", () => {
    const { container } = render(
      <PersonalEditModal
        isOpen={false}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("should render and populate initial data correctly using display values", () => {
    render(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
        canEditTimezone={true}
      />,
    );

    expect(screen.getByDisplayValue("John")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Doe")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Johnny")).toBeInTheDocument();
    expect(
      screen.getByDisplayValue("linkedin.com/in/johndoe"),
    ).toBeInTheDocument();

    expect(screen.getByDisplayValue("Formatted UTC")).toBeInTheDocument();

    const primaryInput = screen.getByDisplayValue("primary@example.com");
    expect(primaryInput).toBeDisabled();
    expect(primaryInput).toHaveAttribute("readonly");

    const altInput = screen.getByDisplayValue("alt@example.com");
    expect(altInput).not.toBeDisabled();
  });

  it("should handle input changes and submit updated data", async () => {
    const user = userEvent.setup();
    render(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
        canEditTimezone={true}
      />,
    );

    const firstNameInput = screen.getByDisplayValue("John");
    await user.clear(firstNameInput);
    await user.type(firstNameInput, "Jane");

    const preferredInput = screen.getByDisplayValue("Johnny");
    await user.clear(preferredInput);
    await user.type(preferredInput, "Janey");

    const saveBtn = screen.getByRole("button", { name: /Save/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith({
        user: expect.objectContaining({
          firstName: "Jane",
          preferredName: "Janey",
          lastName: "Doe",
        }),
      });
    });
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("should validate and show errors when required fields are cleared", async () => {
    const user = userEvent.setup();
    render(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
        canEditTimezone={true}
      />,
    );

    const lastNameInput = screen.getByDisplayValue("Doe");
    await user.clear(lastNameInput);

    const saveBtn = screen.getByRole("button", { name: /Save/i });
    await user.click(saveBtn);

    expect(screen.getByText("Last name is required")).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("should handle adding and removing alternative emails", async () => {
    const user = userEvent.setup();
    render(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
      />,
    );

    const addBtn = screen.getByRole("button", { name: "+" });
    await user.click(addBtn);

    // New email input should be empty; find it by placeholder.
    const emptyAltInputs = screen.getAllByPlaceholderText("Alternative email");
    const newInput = emptyAltInputs.find((input) => input.value === "");
    await user.type(newInput, "new-alt@test.com");

    expect(screen.getByDisplayValue("new-alt@test.com")).toBeInTheDocument();

    // Remove the existing alternative email ("alt@example.com")
    // Locate the container for "alt@example.com" and click the delete button inside it
    const altEmailContainer = screen
      .getByDisplayValue("alt@example.com")
      .closest(".email-edit-item");
    const deleteBtn = within(altEmailContainer).getByRole("button", {
      name: "-",
    });
    await user.click(deleteBtn);

    expect(
      screen.queryByDisplayValue("alt@example.com"),
    ).not.toBeInTheDocument();
  });

  it("should disable timezone selector when canEditTimezone is false", () => {
    render(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
        canEditTimezone={false}
        nextEditableDate="2025-01-01"
      />,
    );

    const timezoneSelect = screen.getByDisplayValue("Formatted UTC");
    expect(timezoneSelect).toBeDisabled();
    expect(
      screen.getByText(/Next editable date: 2025-01-01/),
    ).toBeInTheDocument();
  });

  it("should show communication methods only if user has correct role", () => {
    //  Test the case with permissions (already set in beforeEach)
    const { rerender } = render(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
      />,
    );
    expect(
      screen.getByText("Preferred Communication Method"),
    ).toBeInTheDocument();

    // Test the case without permissions
    useAuth.mockReturnValue({
      roles: [USER_ROLES.STUDENT],
      loading: false,
    });

    rerender(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
      />,
    );
    expect(
      screen.queryByText("Preferred Communication Method"),
    ).not.toBeInTheDocument();
  });
});
