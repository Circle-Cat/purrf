import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import PersonalEditModal from "@/pages/Profile/modals/PersonalEditModal";

vi.mock("@/pages/Profile/utils", () => ({
  CommunicationMethodEnum: {
    Email: "Email",
    GoogleChat: "GoogleChat",
  },
  isValidEmail: (email) => email.includes("@"),
}));

vi.mock("@/components/common/TimezoneSelector", () => ({
  default: ({ value, onChange, isDisabled }) => (
    <select
      value={value}
      onChange={(e) => onChange({ value: e.target.value })}
      disabled={isDisabled}
    >
      <option value="America/New_York">Eastern Time (US & Canada)</option>
    </select>
  ),
}));

vi.mock("@/pages/Profile/modals/Modal.css", () => ({}));

describe("PersonalEditModal Component", () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();

  const initialData = {
    firstName: "John",
    lastName: "Doe",
    preferredName: "Johnny",
    timezone: "America/New_York",
    linkedin: "linkedin.com/in/johndoe",
    communicationMethod: "Email",
    emails: [
      { id: "1", email: "primary@example.com", isPrimary: true },
      { id: "2", email: "alt@example.com", isPrimary: false },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
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

    expect(
      screen.getByDisplayValue("Eastern Time (US & Canada)"),
    ).toBeInTheDocument();
  });

  it("does not render an email editing section", () => {
    render(
      <PersonalEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={initialData}
        onSave={mockOnSave}
        canEditTimezone={true}
      />,
    );

    // Email is managed in Settings now: no email inputs, no "Emails" heading,
    // and no add-email button in this modal.
    expect(
      screen.queryByDisplayValue("primary@example.com"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("alt@example.com"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /emails/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+" })).not.toBeInTheDocument();
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
          // Alternative emails loaded from the backend are passed through
          // unchanged so the save never clears them.
          alternativeEmails: ["alt@example.com"],
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

    const timezoneSelect = screen.getByDisplayValue(
      "Eastern Time (US & Canada)",
    );
    expect(timezoneSelect).toBeDisabled();
    expect(
      screen.getByText(/Next editable date: 2025-01-01/),
    ).toBeInTheDocument();
  });

  it("does not render the communication method selector", () => {
    // The Email/Google Chat selector was gated by the old CONTACT_GOOGLE_CHAT
    // role; it is hidden until its source is reworked off the role system.
    render(
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
