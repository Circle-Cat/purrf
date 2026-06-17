import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";

import ContactSection from "@/pages/Profile/components/ContactSection";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

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
    renderWithRouter(<ContactSection info={BASE_INFO} />);

    expect(
      screen.getByRole("heading", { name: /linkedin link/i }),
    ).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: /email/i })).toBeInTheDocument();
  });

  it("renders LinkedIn link when provided", () => {
    renderWithRouter(<ContactSection info={INFO_WITH_LINKEDIN} />);

    const link = screen.getByRole("link", {
      name: "https://linkedin.com/in/test-user",
    });
    expect(link).toHaveAttribute("href", "https://linkedin.com/in/test-user");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it('renders "Not provided" when LinkedIn link is missing', () => {
    renderWithRouter(<ContactSection info={BASE_INFO} />);

    // Both the missing LinkedIn and the missing primary email read "Not
    // provided"; with no LinkedIn and no emails there are two.
    expect(screen.getAllByText("Not provided")).toHaveLength(2);
  });

  it("shows only the primary email, never the alternatives", () => {
    renderWithRouter(<ContactSection info={INFO_WITH_EMAILS} />);

    expect(screen.getByText("primary@example.com")).toBeInTheDocument();
    expect(screen.queryByText("alt@example.com")).not.toBeInTheDocument();
    // The primary/alternative tags are gone — email is no longer managed here.
    expect(screen.queryByText("Alternative Email")).not.toBeInTheDocument();
    expect(screen.queryByText("Primary Email")).not.toBeInTheDocument();
  });

  it('renders "Not provided" when there is no primary email', () => {
    const altOnly = {
      linkedin: "https://linkedin.com/in/test-user",
      emails: [{ id: 2, email: "alt@example.com", isPrimary: false }],
    };
    renderWithRouter(<ContactSection info={altOnly} />);

    expect(screen.queryByText("alt@example.com")).not.toBeInTheDocument();
    // LinkedIn is present here, so the only "Not provided" is the email.
    expect(screen.getByText("Not provided")).toBeInTheDocument();
  });

  it("links to the Sign in & security settings page to manage email", () => {
    renderWithRouter(<ContactSection info={INFO_WITH_EMAILS} />);

    const manageLink = screen.getByRole("link", { name: "Manage in Settings" });
    expect(manageLink).toHaveAttribute("href", ROUTE_PATHS.SIGN_IN_SECURITY);
  });

  it("renders both LinkedIn and the primary email together", () => {
    renderWithRouter(<ContactSection info={FULL_INFO} />);

    expect(
      screen.getByText("https://linkedin.com/in/test-user"),
    ).toBeInTheDocument();

    expect(screen.getByText("primary@example.com")).toBeInTheDocument();
    expect(screen.queryByText("alt@example.com")).not.toBeInTheDocument();
  });
});
