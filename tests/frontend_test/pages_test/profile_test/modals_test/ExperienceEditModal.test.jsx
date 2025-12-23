import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExperienceEditModal from "@/pages/Profile/modals/ExperienceEditModal";

vi.mock("@/pages/Profile/utils", () => ({
  months: ["January", "February", "March"],
  years: ["2023", "2024", "2025"],
  formatDateFromParts: (m, y) => `${y}-${m}`,
  getDateScore: (y, m) => {
    const months = ["January", "February", "March"];
    return parseInt(y) * 12 + months.indexOf(m);
  },
}));

vi.mock("@/pages/Profile/modals/Modal.css", () => ({}));

describe("ExperienceEditModal", () => {
  const mockInitialData = [
    {
      id: 1,
      title: "Frontend Developer",
      company: "Google",
      startMonth: "January",
      startYear: "2023",
      endMonth: "February",
      endYear: "2024",
      isCurrentlyWorking: false,
    },
  ];

  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn().mockResolvedValue({});

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render initial data correctly", () => {
    render(
      <ExperienceEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={mockInitialData}
        onSave={mockOnSave}
      />,
    );

    expect(screen.getByDisplayValue("Frontend Developer")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Google")).toBeInTheDocument();
    expect(screen.getByDisplayValue("January")).toBeInTheDocument();
  });

  it("should add a new empty experience item when '+' button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <ExperienceEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={[]}
        onSave={mockOnSave}
      />,
    );

    const addButton = screen.getByRole("button", { name: "+" });
    await user.click(addButton);

    // After adding, there should be empty inputs (Title and Company)
    const inputs = screen.getAllByRole("textbox");
    expect(inputs[0].value).toBe(""); // New item is added to the top
  });

  it("should disable and clear end date when 'I am currently working' is checked", async () => {
    const user = userEvent.setup();
    render(
      <ExperienceEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={mockInitialData}
        onSave={mockOnSave}
      />,
    );

    const checkbox = screen.getByLabelText(/I am currently working/i);
    const endMonthSelect = screen.getAllByRole("combobox")[2]; // The third select is End Month

    await user.click(checkbox);

    expect(endMonthSelect).toBeDisabled();
    expect(endMonthSelect.value).toBe("");
  });

  it("should show a validation error when end date is earlier than start date", async () => {
    const user = userEvent.setup();
    const data = [
      {
        ...mockInitialData[0],
        startMonth: "March",
        startYear: "2024",
        endMonth: "January",
        endYear: "2023",
      },
    ];

    render(
      <ExperienceEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={data}
        onSave={mockOnSave}
      />,
    );

    const saveButton = screen.getByRole("button", { name: "Save" });
    await user.click(saveButton);

    expect(
      screen.getByText("End date cannot be earlier than start date"),
    ).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("should show required field errors when saving with empty required fields", async () => {
    const user = userEvent.setup();
    render(
      <ExperienceEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={[{ id: 1, title: "", company: "" }]}
        onSave={mockOnSave}
      />,
    );

    const saveButton = screen.getByRole("button", { name: "Save" });
    await user.click(saveButton);

    expect(screen.getByText("Title is required")).toBeInTheDocument();
    expect(screen.getByText("Company is required")).toBeInTheDocument();
    expect(screen.getByText("Start date is required")).toBeInTheDocument();
  });

  it("should remove the item when delete button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <ExperienceEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={mockInitialData}
        onSave={mockOnSave}
      />,
    );

    const deleteButton = screen.getByRole("button", { name: "-" });
    await user.click(deleteButton);

    expect(
      screen.queryByDisplayValue("Frontend Developer"),
    ).not.toBeInTheDocument();
  });

  it("should submit the correct payload when validation passes", async () => {
    const user = userEvent.setup();
    render(
      <ExperienceEditModal
        isOpen={true}
        onClose={mockOnClose}
        initialData={mockInitialData}
        onSave={mockOnSave}
      />,
    );

    // Update title
    const titleInput = screen.getByDisplayValue("Frontend Developer");
    await user.clear(titleInput);
    await user.type(titleInput, "Senior Engineer");

    const saveButton = screen.getByRole("button", { name: "Save" });
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith({
        profile: {
          workHistory: [
            {
              id: 1,
              title: "Senior Engineer",
              companyOrOrganization: "Google",
              isCurrentJob: false,
              startDate: "2023-January",
              endDate: "2024-February",
            },
          ],
        },
      });
    });

    expect(mockOnClose).toHaveBeenCalled();
  });
});
