import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";

import EmailSection from "@/pages/Profile/components/EmailSection";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

const BASE_INFO = { emails: [] };

const INFO_WITH_PRIMARY = {
  emails: [
    { id: 1, email: "primary@example.com", isPrimary: true },
    { id: 2, email: "alt@example.com", isPrimary: false },
  ],
};

const INFO_ALT_ONLY = {
  emails: [{ id: 2, email: "alt@example.com", isPrimary: false }],
};

describe("EmailSection Component", () => {
  it("renders the Email section header", () => {
    renderWithRouter(<EmailSection info={BASE_INFO} />);

    expect(
      screen.getByRole("heading", { name: /contact email/i }),
    ).toBeInTheDocument();
  });

  it("shows only the primary email, never the alternatives", () => {
    renderWithRouter(<EmailSection info={INFO_WITH_PRIMARY} />);

    expect(screen.getByText("primary@example.com")).toBeInTheDocument();
    expect(screen.queryByText("alt@example.com")).not.toBeInTheDocument();
  });

  it('renders "Not provided" when there is no primary email', () => {
    renderWithRouter(<EmailSection info={INFO_ALT_ONLY} />);

    expect(screen.queryByText("alt@example.com")).not.toBeInTheDocument();
    expect(screen.getByText("Not provided")).toBeInTheDocument();
  });

  it('renders "Not provided" when emails list is empty', () => {
    renderWithRouter(<EmailSection info={BASE_INFO} />);

    expect(screen.getByText("Not provided")).toBeInTheDocument();
  });

  it("links to the Sign in & security settings page to manage email", () => {
    renderWithRouter(<EmailSection info={INFO_WITH_PRIMARY} />);

    const manageLink = screen.getByRole("link", {
      name: /manage in settings/i,
    });
    expect(manageLink).toHaveAttribute("href", ROUTE_PATHS.SIGN_IN_SECURITY);
  });
});
