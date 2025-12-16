import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Profile from "@/pages/Profile";
import { useProfileData } from "@/pages/Profile/hooks/useProfileData";

vi.mock("@/pages/Profile/hooks/useProfileData");

vi.mock("@/pages/Profile/components/ProfileHeader", () => ({
  default: ({ onEditClick }) => (
    <div data-testid="profile-header">
      Profile Header
      <button onClick={onEditClick}>Edit Personal</button>
    </div>
  ),
}));

vi.mock("@/pages/Profile/components/ContactSection", () => ({
  default: () => <div data-testid="contact-section">Contact Section</div>,
}));

vi.mock("@/pages/Profile/components/ExperienceSection", () => ({
  default: ({ onEditClick }) => (
    <div data-testid="experience-section">
      Experience Section
      <button onClick={onEditClick}>Edit Experience</button>
    </div>
  ),
}));

vi.mock("@/pages/Profile/components/EducationSection", () => ({
  default: ({ onEditClick }) => (
    <div data-testid="education-section">
      Education Section
      <button onClick={onEditClick}>Edit Education</button>
    </div>
  ),
}));

vi.mock("@/pages/Profile/components/TrainingSection", () => ({
  default: () => <div data-testid="training-section">Training Section</div>,
}));

vi.mock("@/pages/Profile/modals/PersonalEditModal", () => ({
  default: ({ isOpen, onClose }) =>
    isOpen ? (
      <div data-testid="personal-modal">
        Personal Modal
        <button onClick={onClose}>Close Personal</button>
      </div>
    ) : null,
}));

vi.mock("@/pages/Profile/modals/ExperienceEditModal", () => ({
  default: ({ isOpen, onClose }) =>
    isOpen ? (
      <div data-testid="experience-modal">
        Experience Modal
        <button onClick={onClose}>Close Experience</button>
      </div>
    ) : null,
}));

vi.mock("@/pages/Profile/modals/EducationEditModal", () => ({
  default: ({ isOpen, onClose }) =>
    isOpen ? (
      <div data-testid="education-modal">
        Education Modal
        <button onClick={onClose}>Close Education</button>
      </div>
    ) : null,
}));

describe("Profile Component", () => {
  // Default mock return value
  const mockProfileData = {
    isLoading: false,
    personalInfo: { completedTraining: [] },
    experienceList: [],
    educationList: [],
    canEditPersonalInfo: true,
    nextEditableDate: null,
    handleUpdateProfile: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useProfileData.mockReturnValue(mockProfileData);
  });

  it("renders the loading state when isLoading is true", () => {
    useProfileData.mockReturnValue({ ...mockProfileData, isLoading: true });

    render(<Profile />);
    expect(screen.getByText("Loading profile...")).toBeInTheDocument();
    expect(screen.queryByTestId("profile-header")).not.toBeInTheDocument();
  });

  it("renders all sections when loading is complete", () => {
    render(<Profile />);

    expect(screen.queryByText("Loading profile...")).not.toBeInTheDocument();
    expect(screen.getByTestId("profile-header")).toBeInTheDocument();
    expect(screen.getByTestId("contact-section")).toBeInTheDocument();
    expect(screen.getByTestId("experience-section")).toBeInTheDocument();
    expect(screen.getByTestId("education-section")).toBeInTheDocument();
    expect(screen.getByTestId("training-section")).toBeInTheDocument();
  });

  it("opens and closes the Personal Edit Modal", () => {
    render(<Profile />);

    expect(screen.queryByTestId("personal-modal")).not.toBeInTheDocument();
    const editBtn = screen.getByText("Edit Personal");

    fireEvent.click(editBtn);

    expect(screen.getByTestId("personal-modal")).toBeInTheDocument();
    const closeBtn = screen.getByText("Close Personal");

    fireEvent.click(closeBtn);

    expect(screen.queryByTestId("personal-modal")).not.toBeInTheDocument();
  });

  it("opens and closes the Experience Edit Modal", () => {
    render(<Profile />);

    expect(screen.queryByTestId("experience-modal")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Edit Experience"));

    expect(screen.getByTestId("experience-modal")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Close Experience"));

    expect(screen.queryByTestId("experience-modal")).not.toBeInTheDocument();
  });

  it("opens and closes the Education Edit Modal", () => {
    render(<Profile />);

    expect(screen.queryByTestId("education-modal")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Edit Education"));

    expect(screen.getByTestId("education-modal")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Close Education"));

    expect(screen.queryByTestId("education-modal")).not.toBeInTheDocument();
  });
});
