import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom";

import PackageHealthBox from "@/pages/AdminTraining/components/PackageHealthBox";

// Spec §4.2 (static health check box) / §5: this is the one signal that would have
// caught the 2026-08-29 silent-completion failure, so its three states are
// the whole point of this component.
describe("PackageHealthBox", () => {
  it("warns when the course only completes through a Storyline block", () => {
    render(
      <PackageHealthBox
        config={{
          completesViaStoryline: true,
          completionConfigReadable: true,
          completionPercentage: 100,
        }}
      />,
    );

    expect(
      screen.getByText(
        /finishing every rise lesson will not mark this course complete/i,
      ),
    ).toBeInTheDocument();
  });

  it("says out loud when it could not read the package", () => {
    // Silence here reads as "nothing wrong", which is the 08-29 mistake.
    render(<PackageHealthBox config={{ completionConfigReadable: false }} />);

    expect(
      screen.getByText(/completion behaviour could not be determined/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the trial run is the only check/i),
    ).toBeInTheDocument();
  });

  it("never shows a ceiling for suspend_data", () => {
    render(
      <PackageHealthBox
        config={{ completionConfigReadable: true, completionPercentage: 100 }}
      />,
    );

    expect(screen.queryByText(/4096/)).not.toBeInTheDocument();
  });
});
