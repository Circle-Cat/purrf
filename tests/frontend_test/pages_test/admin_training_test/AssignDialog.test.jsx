import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom";

import AssignDialog from "@/pages/AdminTraining/components/AssignDialog";
import { assignCourse } from "@/api/trainingApi";

vi.mock("@/api/trainingApi");

describe("AssignDialog", () => {
  it("says a repeat assignment does nothing, rather than letting someone hunt for a duplicate", () => {
    render(<AssignDialog course={{ courseId: 5, assignedCount: 124 }} open />);

    expect(
      screen.getByText(/already assigned to 124 people/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/assigning someone a second time does nothing/i),
    ).toBeInTheDocument();
  });

  it("allows an assignment with no deadline, and says so", () => {
    render(<AssignDialog course={{ courseId: 5, assignedCount: 0 }} open />);

    expect(
      screen.getByText(/leave empty if there is no deadline yet/i),
    ).toBeInTheDocument();
  });

  it("sends no deadline field at all when none was given", async () => {
    assignCourse.mockResolvedValue({ data: { trainingId: 9, created: true } });
    render(<AssignDialog course={{ courseId: 5, assignedCount: 0 }} open />);

    await userEvent.type(screen.getByLabelText(/person/i), "11");
    await userEvent.click(screen.getByRole("button", { name: /assign/i }));

    expect(assignCourse).toHaveBeenCalledWith({ userId: 11, courseId: 5 });
  });

  it("names the search gap plainly instead of leaving the field unexplained", () => {
    render(<AssignDialog course={{ courseId: 5, assignedCount: 0 }} open />);

    expect(screen.getByText(/not built yet/i)).toBeInTheDocument();
  });
});
