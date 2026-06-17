import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";

import EmailAddressList from "@/pages/SignInSecurity/components/EmailAddressList";

import "@testing-library/jest-dom/vitest";

const makeEmail = (overrides = {}) => ({
  emailId: 1,
  email: "alice@gmail.com",
  otpConfirmed: true,
  isPrimary: false,
  addedAt: "2026-01-01T00:00:00Z",
  linkedIdentityCount: 0,
  ...overrides,
});

describe("EmailAddressList", () => {
  afterEach(cleanup);

  it("shows a loading placeholder when isLoading is true", () => {
    render(<EmailAddressList emails={[]} isLoading />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no emails", () => {
    render(<EmailAddressList emails={[]} isLoading={false} />);

    expect(screen.getByText("No email addresses yet.")).toBeInTheDocument();
  });

  it("prefers the loading placeholder over the empty state", () => {
    render(<EmailAddressList emails={[]} isLoading />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(
      screen.queryByText("No email addresses yet."),
    ).not.toBeInTheDocument();
  });

  it("renders one row per email with its address", () => {
    const emails = [
      makeEmail({ emailId: 1, email: "alice@gmail.com" }),
      makeEmail({ emailId: 2, email: "bob@gmail.com" }),
    ];

    render(<EmailAddressList emails={emails} isLoading={false} />);

    expect(screen.getByText("alice@gmail.com")).toBeInTheDocument();
    expect(screen.getByText("bob@gmail.com")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("tags the primary email with a Primary badge", () => {
    const emails = [
      makeEmail({ emailId: 1, email: "alice@gmail.com", isPrimary: true }),
      makeEmail({ emailId: 2, email: "bob@gmail.com", isPrimary: false }),
    ];

    render(<EmailAddressList emails={emails} isLoading={false} />);

    const primaryBadges = screen.getAllByText("Primary");
    expect(primaryBadges).toHaveLength(1);
  });

  it("labels verified emails as Verified and unverified as Pending", () => {
    const emails = [
      makeEmail({ emailId: 1, email: "alice@gmail.com", otpConfirmed: true }),
      makeEmail({ emailId: 2, email: "bob@gmail.com", otpConfirmed: false }),
    ];

    render(<EmailAddressList emails={emails} isLoading={false} />);

    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });
});
