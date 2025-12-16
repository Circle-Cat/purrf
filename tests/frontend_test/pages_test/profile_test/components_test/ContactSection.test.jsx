import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import ContactSection from "@/pages/Profile/components/ContactSection";

const BASE_INFO = {
  linkedin: null,
  emails: [],
};

const INFO_WITH_LINKEDIN = {
  ...BASE_INFO,
  linkedin: "https://linkedin.com/in/test-user",
};

const INFO_WITH_EMAILS = {
  ...BASE_INFO,
  emails: [
    {
      id: 1,
      email: "primary@example.com",
      isPrimary: true,
    },
    {
      id: 2,
      email: "alt@example.com",
      isPrimary: false,
    },
  ],
};

const FULL_INFO = {
  linkedin: "https://linkedin.com/in/test-user",
  emails: [
    {
      id: 1,
      email: "primary@example.com",
      isPrimary: true,
    },
    {
      id: 2,
      email: "alt@example.com",
      isPrimary: false,
    },
  ],
};

describe("ContactSection Component", () => {
  it("renders section headers", () => {
    render(<ContactSection info={BASE_INFO} />);

    expect(
      screen.getByRole("heading", { name: /linkedin link/i }),
    ).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: /email/i })).toBeInTheDocument();
  });

  it("renders LinkedIn link when provided", () => {
    render(<ContactSection info={INFO_WITH_LINKEDIN} />);

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://linkedin.com/in/test-user");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it('renders "Not provided" when LinkedIn link is missing', () => {
    render(<ContactSection info={BASE_INFO} />);

    expect(screen.getByText("Not provided")).toBeInTheDocument();
  });

  it("renders email list correctly", () => {
    render(<ContactSection info={INFO_WITH_EMAILS} />);

    expect(screen.getByText("primary@example.com")).toBeInTheDocument();

    expect(screen.getByText("alt@example.com")).toBeInTheDocument();
  });

  it("renders primary and alternative email tags correctly", () => {
    render(<ContactSection info={INFO_WITH_EMAILS} />);

    const primaryTag = screen.getByText("Primary Email");
    expect(primaryTag).toBeInTheDocument();
    expect(primaryTag).toHaveClass("email-tag primary");

    const alternativeTag = screen.getByText("Alternative Email");
    expect(alternativeTag).toBeInTheDocument();
    expect(alternativeTag).toHaveClass("email-tag alternative");
  });

  it("renders both LinkedIn and email sections together", () => {
    render(<ContactSection info={FULL_INFO} />);

    expect(
      screen.getByText("https://linkedin.com/in/test-user"),
    ).toBeInTheDocument();

    expect(screen.getByText("primary@example.com")).toBeInTheDocument();

    expect(screen.getByText("alt@example.com")).toBeInTheDocument();
  });
});
