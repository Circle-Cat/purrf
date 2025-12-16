import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

import ExperienceSection from "@/pages/Profile/components/ExperienceSection";
import { formatTimeDuration } from "@/pages/Profile/utils";

vi.mock("@/pages/Profile/utils", () => ({
  formatTimeDuration: vi.fn(),
}));

const BASE_EXP_ITEM = {
  startMonth: "January",
  startYear: "2020",
  endMonth: "June",
  endYear: "2023",
  isCurrentlyWorking: false,
};

const EXPERIENCE_FIXTURES = {
  single: [
    {
      id: 1,
      title: "Software Engineer",
      company: "Tech Corp",
      ...BASE_EXP_ITEM,
    },
  ],

  multiple: [
    {
      id: 1,
      title: "Frontend Engineer",
      company: "Company A",
      ...BASE_EXP_ITEM,
    },
    {
      id: 2,
      title: "Senior Engineer",
      company: "Company B",
      startMonth: "July",
      startYear: "2023",
      endMonth: null,
      endYear: null,
      isCurrentlyWorking: true,
    },
  ],
};

describe("ExperienceSection Component", () => {
  const onEditClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    formatTimeDuration.mockReturnValue("Jan 2020 - Jun 2023");
  });

  it("renders section header and edit button", () => {
    render(<ExperienceSection list={[]} onEditClick={onEditClick} />);

    expect(
      screen.getByRole("heading", { name: /experience/i }),
    ).toBeInTheDocument();

    const editButton = screen.getByRole("button", {
      name: /edit experience/i,
    });
    expect(editButton).toBeInTheDocument();
  });

  it("calls onEditClick when edit button is clicked", () => {
    render(<ExperienceSection list={[]} onEditClick={onEditClick} />);

    fireEvent.click(screen.getByRole("button", { name: /edit experience/i }));

    expect(onEditClick).toHaveBeenCalledTimes(1);
  });

  it("renders empty state when list is null or empty", () => {
    const { rerender } = render(
      <ExperienceSection list={[]} onEditClick={onEditClick} />,
    );

    expect(screen.getByText("No experience added.")).toBeInTheDocument();

    rerender(<ExperienceSection list={null} onEditClick={onEditClick} />);

    expect(screen.getByText("No experience added.")).toBeInTheDocument();
  });

  it("renders experience list when data is provided", () => {
    render(
      <ExperienceSection
        list={EXPERIENCE_FIXTURES.single}
        onEditClick={onEditClick}
      />,
    );

    expect(screen.getByText("Software Engineer")).toBeInTheDocument();

    expect(screen.getByText("Tech Corp")).toBeInTheDocument();

    expect(screen.getByText("Jan 2020 - Jun 2023")).toBeInTheDocument();
  });

  it("renders multiple experience items correctly", () => {
    render(
      <ExperienceSection
        list={EXPERIENCE_FIXTURES.multiple}
        onEditClick={onEditClick}
      />,
    );

    expect(screen.getByText("Frontend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Senior Engineer")).toBeInTheDocument();
  });

  it("calls formatTimeDuration with correct arguments", () => {
    render(
      <ExperienceSection
        list={EXPERIENCE_FIXTURES.single}
        onEditClick={onEditClick}
      />,
    );

    expect(formatTimeDuration).toHaveBeenCalledWith(
      "January",
      "2020",
      "June",
      "2023",
      false,
    );
  });

  it("handles currently working experience correctly", () => {
    render(
      <ExperienceSection
        list={[EXPERIENCE_FIXTURES.multiple[1]]}
        onEditClick={onEditClick}
      />,
    );

    expect(formatTimeDuration).toHaveBeenCalledWith(
      "July",
      "2023",
      null,
      null,
      true,
    );
  });
});
