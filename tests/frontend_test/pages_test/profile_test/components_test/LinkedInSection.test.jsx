import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import LinkedInSection from "@/pages/Profile/components/LinkedInSection";

const BASE_INFO = { linkedin: null };
const INFO_WITH_LINKEDIN = { linkedin: "https://linkedin.com/in/test-user" };

describe("LinkedInSection Component", () => {
  it("renders the LinkedIn link section header", () => {
    render(<LinkedInSection info={BASE_INFO} />);

    expect(
      screen.getByRole("heading", { name: /linkedin link/i }),
    ).toBeInTheDocument();
  });

  it("renders LinkedIn link when provided", () => {
    render(<LinkedInSection info={INFO_WITH_LINKEDIN} />);

    const link = screen.getByRole("link", {
      name: "https://linkedin.com/in/test-user",
    });
    expect(link).toHaveAttribute("href", "https://linkedin.com/in/test-user");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it('renders "Not provided" when LinkedIn link is missing', () => {
    render(<LinkedInSection info={BASE_INFO} />);

    expect(screen.getByText("Not provided")).toBeInTheDocument();
  });
});
