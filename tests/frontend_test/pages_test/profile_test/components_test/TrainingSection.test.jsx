import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

import TrainingSection from "@/pages/Profile/components/TrainingSection";
import { formatDateFromParts } from "@/pages/Profile/utils";

vi.mock("@/pages/Profile/utils", () => ({
  formatDateFromParts: vi.fn(),
}));

const BASE_DATE_PARTS = {
  completionMonth: "January",
  completionYear: "2023",
  dueMonth: "February",
  dueYear: "2023",
};

const TRAINING_FIXTURES = {
  single: [
    {
      id: 1,
      name: "Security Training",
      status: "done",
      link: "https://example.com/cert",
      ...BASE_DATE_PARTS,
    },
  ],

  statusMix: [
    {
      id: 1,
      name: "Task 1",
      status: "done",
      link: "",
      ...BASE_DATE_PARTS,
    },
    {
      id: 2,
      name: "Task 2",
      status: "pending",
      link: "",
      ...BASE_DATE_PARTS,
    },
  ],

  withAndWithoutLink: [
    {
      id: 1,
      name: "With Link",
      status: "done",
      link: "http://test.com",
      ...BASE_DATE_PARTS,
    },
    {
      id: 2,
      name: "No Link",
      status: "done",
      link: null,
      ...BASE_DATE_PARTS,
    },
  ],

  invalidDate: [
    {
      id: 1,
      name: "Invalid Date Training",
      status: "done",
      completionMonth: null,
      completionYear: null,
      dueMonth: null,
      dueYear: null,
      link: "",
    },
  ],
};

describe("TrainingSection Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    formatDateFromParts.mockReturnValue(true);
  });

  it("renders the header correctly", () => {
    render(<TrainingSection list={[]} />);

    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent(
      "Training",
    );
  });

  it("renders empty state when list is empty or null", () => {
    const { rerender } = render(<TrainingSection list={[]} />);
    expect(screen.getByText("No training records found.")).toBeInTheDocument();

    rerender(<TrainingSection list={null} />);
    expect(screen.getByText("No training records found.")).toBeInTheDocument();
  });

  it("renders table with correct data when list is provided", () => {
    render(<TrainingSection list={TRAINING_FIXTURES.single} />);

    // Header
    expect(screen.getByText("Name")).toBeInTheDocument();

    // Row data
    expect(screen.getByText("Security Training")).toBeInTheDocument();

    expect(screen.getByText("Jan 2023")).toBeInTheDocument();
    expect(screen.getByText("Feb 2023")).toBeInTheDocument();
  });

  it("renders status correctly based on status value", () => {
    render(<TrainingSection list={TRAINING_FIXTURES.statusMix} />);

    const completedTag = screen.getByText("Completed");
    expect(completedTag).toBeInTheDocument();
    expect(completedTag).toHaveClass("training-tag done");

    const pendingTag = screen.getByText("Not Completed");
    expect(pendingTag).toBeInTheDocument();
    expect(pendingTag).toHaveClass("training-tag pending");
  });

  it('falls back to "-" when date validation fails', () => {
    formatDateFromParts.mockReturnValue(null);

    render(<TrainingSection list={TRAINING_FIXTURES.invalidDate} />);

    // Two date columns => at least two "-"
    expect(screen.getAllByText("-").length).toBeGreaterThanOrEqual(2);
  });

  it("renders links correctly based on link value", () => {
    render(<TrainingSection list={TRAINING_FIXTURES.withAndWithoutLink} />);

    const link = screen.getByRole("link", { name: /view link/i });
    expect(link).toHaveAttribute("href", "http://test.com");
    expect(link).toHaveAttribute("target", "_blank");

    const noLinkRow = screen.getByText("No Link").closest("tr");
    expect(noLinkRow).toHaveTextContent("-");
  });
});
