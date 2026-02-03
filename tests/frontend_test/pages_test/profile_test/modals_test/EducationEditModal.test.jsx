import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EducationEditModal from "@/pages/Profile/modals/EducationEditModal";

vi.mock("@/pages/Profile/utils", () => ({
  months: ["January", "February", "March"],
  years: ["2023", "2024", "2025"],
  years60Range: ["2023", "2024", "2025"],
  DegreeEnum: {
    Bachelor: "Bachelor",
    Master: "Master",
  },
  formatDateFromParts: (m, y) => `${y}-${m}`,
  getDateScore: (y, m) => {
    const months = ["January", "February", "March"];
    return parseInt(y) * 12 + months.indexOf(m);
  },
}));

vi.mock("@/pages/Profile/modals/Modal.css", () => ({}));

describe("EducationEditModal", () => {
  const mockInitialData = [
    {
      id: 1,
      institution: "MIT",
      degree: "Bachelor",
      field: "Computer Science",
      startMonth: "January",
      startYear: "2023",
      endMonth: "February",
      endYear: "2024",
    },
  ];

  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn().mockResolvedValue({});

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render initial data correctly", () => {
    render(
      <EducationEditModal
        isOpen
        onClose={mockOnClose}
        initialData={mockInitialData}
        onSave={mockOnSave}
      />,
    );

    expect(screen.getByDisplayValue("MIT")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Bachelor")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Computer Science")).toBeInTheDocument();
    expect(screen.getByDisplayValue("January")).toBeInTheDocument();
  });

  it("should add a new empty education item when '+' is clicked", async () => {
    const user = userEvent.setup();

    render(
      <EducationEditModal
        isOpen
        onClose={mockOnClose}
        initialData={[]}
        onSave={mockOnSave}
      />,
    );

    await user.click(screen.getByRole("button", { name: "+" }));

    const inputs = screen.getAllByRole("textbox");
    expect(inputs[0].value).toBe("");
  });

  it("should show validation errors for required fields", async () => {
    const user = userEvent.setup();

    render(
      <EducationEditModal
        isOpen
        onClose={mockOnClose}
        initialData={[{ id: 1, institution: "", degree: "", field: "" }]}
        onSave={mockOnSave}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(screen.getByText("School is required")).toBeInTheDocument();
    expect(screen.getByText("Degree is required")).toBeInTheDocument();
    expect(screen.getByText("Field of study is required")).toBeInTheDocument();
    expect(screen.getByText("Start date is required")).toBeInTheDocument();
    expect(screen.getByText("End date is required")).toBeInTheDocument();
  });

  it("should show error when end date is earlier than start date", async () => {
    const user = userEvent.setup();

    render(
      <EducationEditModal
        isOpen
        onClose={mockOnClose}
        initialData={[
          {
            ...mockInitialData[0],
            startMonth: "March",
            startYear: "2024",
            endMonth: "January",
            endYear: "2023",
          },
        ]}
        onSave={mockOnSave}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      screen.getByText("End date cannot be earlier than start date"),
    ).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("should show error when start date is in the future", async () => {
    vi.useFakeTimers();
    const mockNow = new Date(2023, 0, 1);
    vi.setSystemTime(mockNow);

    render(
      <EducationEditModal
        isOpen
        onClose={mockOnClose}
        initialData={[
          {
            ...mockInitialData[0],
            startMonth: "March",
            startYear: "2024",
            endMonth: "January",
            endYear: "2025",
          },
        ]}
        onSave={mockOnSave}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      screen.getByText("Start date cannot be in the future"),
    ).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();

    vi.useRealTimers();
  });

  it("should delete an education item", async () => {
    const user = userEvent.setup();

    render(
      <EducationEditModal
        isOpen
        onClose={mockOnClose}
        initialData={mockInitialData}
        onSave={mockOnSave}
      />,
    );

    await user.click(screen.getByRole("button", { name: "-" }));

    expect(screen.queryByDisplayValue("MIT")).not.toBeInTheDocument();
  });

  it("should submit correct payload when validation passes", async () => {
    const user = userEvent.setup();

    render(
      <EducationEditModal
        isOpen
        onClose={mockOnClose}
        initialData={mockInitialData}
        onSave={mockOnSave}
      />,
    );

    const schoolInput = screen.getByDisplayValue("MIT");
    await user.clear(schoolInput);
    await user.type(schoolInput, "Stanford");

    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith({
        education: [
          {
            id: 1,
            school: "Stanford",
            degree: "Bachelor",
            fieldOfStudy: "Computer Science",
            startDate: "2023-January",
            endDate: "2024-February",
          },
        ],
      });
    });

    expect(mockOnClose).toHaveBeenCalled();
  });
});
