import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import EducationSection from "@/pages/Profile/components/EducationSection";
import { formatTimeDuration } from "@/pages/Profile/utils";

vi.mock("@/pages/Profile/utils", () => ({
  formatTimeDuration: vi.fn(),
}));

const BASE_EDU_ITEM = {
  startMonth: "January",
  startYear: "2018",
  endMonth: "June",
  endYear: "2022",
};

const EDUCATION_FIXTURES = {
  single: [
    {
      id: 1,
      institution: "University of Testing",
      degree: "Bachelor",
      field: "Computer Science",
      ...BASE_EDU_ITEM,
    },
  ],

  multiple: [
    {
      id: 1,
      institution: "University A",
      degree: "Bachelor",
      field: "Computer Science",
      ...BASE_EDU_ITEM,
    },
    {
      id: 2,
      institution: "University B",
      degree: "Master",
      field: "Software Engineering",
      startMonth: "September",
      startYear: "2022",
      endMonth: "June",
      endYear: "2024",
    },
  ],
};

describe("EducationSection Component", () => {
  const onEditClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    formatTimeDuration.mockReturnValue("Jan 2018 - Jun 2022");
  });

  it("renders section header and edit button", () => {
    render(<EducationSection list={[]} onEditClick={onEditClick} />);

    expect(
      screen.getByRole("heading", { name: /education/i }),
    ).toBeInTheDocument();

    const editButton = screen.getByRole("button", {
      name: /edit education/i,
    });
    expect(editButton).toBeInTheDocument();
  });

  it("calls onEditClick when edit button is clicked", () => {
    render(<EducationSection list={[]} onEditClick={onEditClick} />);

    fireEvent.click(screen.getByRole("button", { name: /edit education/i }));

    expect(onEditClick).toHaveBeenCalledTimes(1);
  });

  it("renders empty state when education list is empty", () => {
    render(<EducationSection list={[]} onEditClick={onEditClick} />);

    expect(screen.getByText("No education added.")).toBeInTheDocument();
  });

  it("renders education list when data is provided", () => {
    render(
      <EducationSection
        list={EDUCATION_FIXTURES.single}
        onEditClick={onEditClick}
      />,
    );

    expect(screen.getByText("University of Testing")).toBeInTheDocument();

    expect(
      screen.getByText("Bachelor's degree, Computer Science"),
    ).toBeInTheDocument();

    expect(screen.getByText("Jan 2018 - Jun 2022")).toBeInTheDocument();
  });

  it("renders multiple education items correctly", () => {
    render(
      <EducationSection
        list={EDUCATION_FIXTURES.multiple}
        onEditClick={onEditClick}
      />,
    );

    expect(screen.getByText("University A")).toBeInTheDocument();
    expect(screen.getByText("University B")).toBeInTheDocument();

    // duration text should appear for each item
    const durations = screen.getAllByText("Jan 2018 - Jun 2022");
    expect(durations.length).toBeGreaterThanOrEqual(1);
  });

  it("calls formatTimeDuration with correct arguments", () => {
    render(
      <EducationSection
        list={EDUCATION_FIXTURES.single}
        onEditClick={onEditClick}
      />,
    );

    expect(formatTimeDuration).toHaveBeenCalledWith(
      "January",
      "2018",
      "June",
      "2022",
    );
  });
});
