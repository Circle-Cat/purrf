import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom";

import DeactivateDialog from "@/pages/AdminTraining/components/DeactivateDialog";

describe("DeactivateDialog", () => {
  it("weighs the decision by counting people, not by asking twice", () => {
    render(
      <DeactivateDialog
        course={{ courseId: 5, assignedCount: 61, unfinishedCount: 23 }}
        open
      />,
    );

    expect(
      screen.getByText(/61 people already assigned keep their access/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/23 of them have not finished yet/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/nothing is deleted/i)).toBeInTheDocument();
    expect(screen.queryByText(/are you sure/i)).not.toBeInTheDocument();
  });

  it("says plainly that it can be turned back on", () => {
    render(
      <DeactivateDialog
        course={{ courseId: 5, assignedCount: 0, unfinishedCount: 0 }}
        open
      />,
    );

    expect(
      screen.getByText(/turn it back on at any time/i),
    ).toBeInTheDocument();
  });
});
