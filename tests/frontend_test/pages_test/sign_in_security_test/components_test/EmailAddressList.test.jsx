import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";
import userEvent from "@testing-library/user-event";

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

  describe("Set as primary action", () => {
    it("offers Set as primary only for verified, non-primary emails", () => {
      const emails = [
        makeEmail({ emailId: 1, isPrimary: true, otpConfirmed: true }),
        makeEmail({ emailId: 2, isPrimary: false, otpConfirmed: true }),
        makeEmail({ emailId: 3, isPrimary: false, otpConfirmed: false }),
      ];

      render(
        <EmailAddressList
          emails={emails}
          isLoading={false}
          onSetPrimary={vi.fn()}
        />,
      );

      // Only the verified, non-primary row (emailId 2) gets the button.
      expect(
        screen.getAllByRole("button", { name: "Set as primary" }),
      ).toHaveLength(1);
    });

    it("does not offer Set as primary for the primary email", () => {
      const emails = [makeEmail({ emailId: 1, isPrimary: true })];

      render(
        <EmailAddressList
          emails={emails}
          isLoading={false}
          onSetPrimary={vi.fn()}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Set as primary" }),
      ).not.toBeInTheDocument();
    });

    it("does not offer Set as primary for an unverified email", () => {
      const emails = [
        makeEmail({ emailId: 1, isPrimary: false, otpConfirmed: false }),
      ];

      render(
        <EmailAddressList
          emails={emails}
          isLoading={false}
          onSetPrimary={vi.fn()}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Set as primary" }),
      ).not.toBeInTheDocument();
    });

    it("calls onSetPrimary with the row when clicked", async () => {
      const user = userEvent.setup();
      const onSetPrimary = vi.fn().mockResolvedValue();
      const target = makeEmail({
        emailId: 2,
        email: "bob@gmail.com",
        isPrimary: false,
        otpConfirmed: true,
      });

      render(
        <EmailAddressList
          emails={[target]}
          isLoading={false}
          onSetPrimary={onSetPrimary}
        />,
      );

      await user.click(screen.getByRole("button", { name: "Set as primary" }));

      expect(onSetPrimary).toHaveBeenCalledWith(target);
    });

    it("shows a busy label and disables actions while promoting", async () => {
      const user = userEvent.setup();
      let resolve;
      const onSetPrimary = vi.fn(
        () =>
          new Promise((r) => {
            resolve = r;
          }),
      );
      const emails = [
        makeEmail({ emailId: 1, email: "a@gmail.com" }),
        makeEmail({ emailId: 2, email: "b@gmail.com" }),
      ];

      render(
        <EmailAddressList
          emails={emails}
          isLoading={false}
          onSetPrimary={onSetPrimary}
        />,
      );

      const buttons = screen.getAllByRole("button", { name: "Set as primary" });
      await user.click(buttons[0]);

      // The clicked row shows the busy label; every button is disabled.
      expect(screen.getByText("Setting…")).toBeInTheDocument();
      screen
        .getAllByRole("button")
        .forEach((button) => expect(button).toBeDisabled());

      resolve();
      await waitFor(() =>
        expect(screen.queryByText("Setting…")).not.toBeInTheDocument(),
      );
    });
  });
});
