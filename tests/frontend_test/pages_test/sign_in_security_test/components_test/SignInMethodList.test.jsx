import {
  render,
  screen,
  cleanup,
  within,
  waitFor,
} from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import SignInMethodList from "@/pages/SignInSecurity/components/SignInMethodList";

import "@testing-library/jest-dom/vitest";

const makeIdentity = (overrides = {}) => ({
  identityId: 1,
  subjectIdentifier: "google-oauth2|123",
  emailClaim: "alice@gmail.com",
  linkedAt: "2026-01-01T00:00:00Z",
  lastUsedAt: "2026-02-01T00:00:00Z",
  ...overrides,
});

const makeEmail = (overrides = {}) => ({
  emailId: 1,
  email: "alice@gmail.com",
  otpConfirmed: true,
  isPrimary: false,
  addedAt: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("SignInMethodList", () => {
  afterEach(cleanup);

  it("shows a loading placeholder when isLoading is true", () => {
    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={[]}
        isLoading
      />,
    );

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no addresses", () => {
    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={[]}
        isLoading={false}
      />,
    );

    expect(screen.getByText("No sign-in methods yet.")).toBeInTheDocument();
  });

  it("never shows an Unverified badge or a Verify action", () => {
    render(
      <SignInMethodList
        emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
        internalIdentities={[]}
        externalIdentities={[makeIdentity()]}
        isLoading={false}
        onUnlink={vi.fn()}
      />,
    );

    expect(screen.queryByText("Unverified")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Verify" }),
    ).not.toBeInTheDocument();
  });

  describe("Address grouping", () => {
    it("collapses an email and the identity that claims it into one row", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ isPrimary: true })]}
          internalIdentities={[]}
          externalIdentities={[makeIdentity()]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(screen.getAllByRole("listitem")).toHaveLength(1);
      expect(screen.getAllByText("alice@gmail.com")).toHaveLength(1);
    });

    it("matches an email to its identity claim regardless of casing", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ email: "Alice@Gmail.com" })]}
          internalIdentities={[]}
          externalIdentities={[makeIdentity({ emailClaim: "alice@gmail.com" })]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(screen.getAllByRole("listitem")).toHaveLength(1);
    });

    it("renders distinct addresses as separate rows", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
          internalIdentities={[]}
          externalIdentities={[makeIdentity()]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      expect(rows).toHaveLength(2);
      expect(screen.getByText("alice@gmail.com")).toBeInTheDocument();
      expect(screen.getByText("backup@x.com")).toBeInTheDocument();
    });

    it("puts the primary-contact address first", () => {
      render(
        <SignInMethodList
          emails={[
            makeEmail({ emailId: 3, email: "backup@x.com", isPrimary: false }),
            makeEmail({ emailId: 1, email: "main@x.com", isPrimary: true }),
          ]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      expect(within(rows[0]).getByText("main@x.com")).toBeInTheDocument();
      expect(within(rows[1]).getByText("backup@x.com")).toBeInTheDocument();
    });

    it("renders an unconfirmed contact-only email as its own row", () => {
      render(
        <SignInMethodList
          emails={[
            makeEmail({ emailId: 3, email: "new@x.com", otpConfirmed: false }),
          ]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
        />,
      );

      expect(
        screen.queryByText("No sign-in methods yet."),
      ).not.toBeInTheDocument();
      expect(screen.getByText("new@x.com")).toBeInTheDocument();
      // Not confirmed → no Email OTP capability chip.
      expect(screen.queryByText("Email OTP")).not.toBeInTheDocument();
    });

    it("renders a claimless identity as a lone provider row with no chips", () => {
      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={[
            makeIdentity({
              subjectIdentifier: "google-oauth2|1",
              emailClaim: null,
            }),
          ]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      expect(rows).toHaveLength(1);
      expect(within(rows[0]).getByText("Google account")).toBeInTheDocument();
      expect(within(rows[0]).queryByText(/@/)).not.toBeInTheDocument();
    });
  });

  describe("Capability chips", () => {
    it("labels a Google identity's address 'Google account'", () => {
      render(
        <SignInMethodList
          emails={[makeEmail()]}
          internalIdentities={[]}
          externalIdentities={[makeIdentity()]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(screen.getByText("Google account")).toBeInTheDocument();
    });

    it("shows an Email OTP chip on a confirmed email", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
        />,
      );

      expect(screen.getByText("Email OTP")).toBeInTheDocument();
    });

    it("shows both chips when an address has a Google sign-in and Email OTP", () => {
      render(
        <SignInMethodList
          emails={[makeEmail()]}
          internalIdentities={[]}
          externalIdentities={[makeIdentity()]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      expect(within(rows[0]).getByText("Google account")).toBeInTheDocument();
      expect(within(rows[0]).getByText("Email OTP")).toBeInTheDocument();
    });

    it("shows a single Email OTP chip for an email| identity on a confirmed email", () => {
      render(
        <SignInMethodList
          emails={[makeEmail()]}
          internalIdentities={[]}
          externalIdentities={[
            makeIdentity({ subjectIdentifier: "email|abc" }),
          ]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(screen.getAllByText("Email OTP")).toHaveLength(1);
    });
  });

  describe("Status badges", () => {
    it("tags an internal identity's address Internal", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ email: "work@circlecat.org", isPrimary: true })]}
          internalIdentities={[
            makeIdentity({
              subjectIdentifier: "google-oauth2|work",
              emailClaim: "work@circlecat.org",
            }),
          ]}
          externalIdentities={[]}
          isLoading={false}
        />,
      );

      expect(screen.getByText("Internal")).toBeInTheDocument();
    });

    it("badges the primary contact address", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ isPrimary: true })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
        />,
      );

      expect(screen.getByText("Primary contact")).toBeInTheDocument();
    });

    it("badges the address backing the current session", () => {
      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={[
            makeIdentity({ identityId: 1, isCurrentSession: true }),
            makeIdentity({
              identityId: 2,
              subjectIdentifier: "google-oauth2|2",
              emailClaim: "bob@gmail.com",
            }),
          ]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      expect(within(rows[0]).getByText("Current session")).toBeInTheDocument();
      expect(
        within(rows[1]).queryByText("Current session"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Remove sign-in identity", () => {
    it("offers 'Remove Google account sign-in' for an external identity", () => {
      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={[makeIdentity()]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(
        screen.getByRole("button", { name: "Remove Google account sign-in" }),
      ).toBeInTheDocument();
    });

    it("never offers to remove an internal identity", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ email: "work@circlecat.org", isPrimary: true })]}
          internalIdentities={[
            makeIdentity({
              subjectIdentifier: "google-oauth2|work",
              emailClaim: "work@circlecat.org",
            }),
          ]}
          externalIdentities={[]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(
        screen.queryByRole("button", { name: /Remove .* sign-in/ }),
      ).not.toBeInTheDocument();
    });

    it("does not offer to remove the current-session identity", () => {
      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={[
            makeIdentity({ identityId: 1, isCurrentSession: true }),
            makeIdentity({
              identityId: 2,
              subjectIdentifier: "google-oauth2|2",
              emailClaim: "bob@gmail.com",
            }),
          ]}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      expect(
        within(rows[0]).queryByRole("button", { name: /sign-in/ }),
      ).not.toBeInTheDocument();
      expect(
        within(rows[1]).getByRole("button", {
          name: "Remove Google account sign-in",
        }),
      ).toBeInTheDocument();
    });

    it("calls onUnlink with the identity when clicked", async () => {
      const user = userEvent.setup();
      const onUnlink = vi.fn().mockResolvedValue();
      const identity = makeIdentity({ emailClaim: "bob@gmail.com" });

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={[identity]}
          isLoading={false}
          onUnlink={onUnlink}
        />,
      );

      await user.click(
        screen.getByRole("button", { name: "Remove Google account sign-in" }),
      );

      expect(onUnlink).toHaveBeenCalledWith(identity);
    });

    it("shows a busy label and disables actions while unlinking", async () => {
      const user = userEvent.setup();
      let resolve;
      const onUnlink = vi.fn(
        () =>
          new Promise((r) => {
            resolve = r;
          }),
      );

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={[makeIdentity({ emailClaim: "bob@gmail.com" })]}
          isLoading={false}
          onUnlink={onUnlink}
        />,
      );

      await user.click(
        screen.getByRole("button", { name: "Remove Google account sign-in" }),
      );

      expect(screen.getByText("Removing…")).toBeInTheDocument();
      screen
        .getAllByRole("button")
        .forEach((button) => expect(button).toBeDisabled());

      resolve();
      await waitFor(() =>
        expect(screen.queryByText("Removing…")).not.toBeInTheDocument(),
      );
    });
  });

  describe("Remove email", () => {
    it("offers Remove email on a non-primary email and calls onRemove", async () => {
      const user = userEvent.setup();
      const onRemove = vi.fn().mockResolvedValue();
      const email = makeEmail({ emailId: 3, email: "backup@x.com" });

      render(
        <SignInMethodList
          emails={[email]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
          onRemove={onRemove}
        />,
      );

      await user.click(screen.getByRole("button", { name: "Remove email" }));
      expect(onRemove).toHaveBeenCalledWith(email);
    });

    it("does not offer Remove email on the primary contact", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ isPrimary: true })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
          onRemove={vi.fn()}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Remove email" }),
      ).not.toBeInTheDocument();
    });

    it("does not offer Remove email when onRemove is not provided", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Remove email" }),
      ).not.toBeInTheDocument();
    });

    it("shows a busy label and disables actions while removing", async () => {
      const user = userEvent.setup();
      let resolve;
      const onRemove = vi.fn(
        () =>
          new Promise((r) => {
            resolve = r;
          }),
      );

      render(
        <SignInMethodList
          emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
          onRemove={onRemove}
        />,
      );

      await user.click(screen.getByRole("button", { name: "Remove email" }));

      expect(screen.getByText("Removing…")).toBeInTheDocument();
      screen
        .getAllByRole("button")
        .forEach((button) => expect(button).toBeDisabled());

      resolve();
      await waitFor(() =>
        expect(screen.queryByText("Removing…")).not.toBeInTheDocument(),
      );
    });
  });

  describe("Set as primary contact", () => {
    it("offers the action for a verified, non-primary email on a non-internal account", async () => {
      const user = userEvent.setup();
      const onSetPrimary = vi.fn().mockResolvedValue();
      const email = makeEmail({ emailId: 3, email: "backup@x.com" });

      render(
        <SignInMethodList
          emails={[email]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
          onSetPrimary={onSetPrimary}
        />,
      );

      await user.click(
        screen.getByRole("button", { name: "Set as primary contact" }),
      );
      expect(onSetPrimary).toHaveBeenCalledWith(email);
    });

    it("does not offer the action on the primary or an unverified email", () => {
      render(
        <SignInMethodList
          emails={[
            makeEmail({ emailId: 1, email: "main@x.com", isPrimary: true }),
            makeEmail({
              emailId: 2,
              email: "new@x.com",
              otpConfirmed: false,
            }),
          ]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
          onSetPrimary={vi.fn()}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Set as primary contact" }),
      ).not.toBeInTheDocument();
    });

    it("never offers the action on an internal account", () => {
      // Internal accounts keep a corp-managed primary; the action is withheld
      // even for a qualifying non-corp email.
      render(
        <SignInMethodList
          emails={[
            makeEmail({ email: "work@circlecat.org", isPrimary: true }),
            makeEmail({ emailId: 2, email: "personal@gmail.com" }),
          ]}
          internalIdentities={[
            makeIdentity({
              subjectIdentifier: "google-oauth2|work",
              emailClaim: "work@circlecat.org",
            }),
          ]}
          externalIdentities={[]}
          isLoading={false}
          onSetPrimary={vi.fn()}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Set as primary contact" }),
      ).not.toBeInTheDocument();
    });

    it("offers no action without onSetPrimary", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Set as primary contact" }),
      ).not.toBeInTheDocument();
    });

    it("shows a busy label and disables actions while setting the primary", async () => {
      const user = userEvent.setup();
      let resolve;
      const onSetPrimary = vi.fn(
        () =>
          new Promise((r) => {
            resolve = r;
          }),
      );

      render(
        <SignInMethodList
          emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
          onSetPrimary={onSetPrimary}
        />,
      );

      await user.click(
        screen.getByRole("button", { name: "Set as primary contact" }),
      );

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

  describe("Multi-path hint", () => {
    it("warns when an address has both a removable sign-in and a removable Email OTP", () => {
      render(
        <SignInMethodList
          emails={[makeEmail()]}
          internalIdentities={[]}
          externalIdentities={[makeIdentity()]}
          isLoading={false}
          onUnlink={vi.fn()}
          onRemove={vi.fn()}
        />,
      );

      expect(
        screen.getByText(/won.t fully disconnect this address/i),
      ).toBeInTheDocument();
    });

    it("shows no hint for an address with only Email OTP", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ emailId: 3, email: "backup@x.com" })]}
          internalIdentities={[]}
          externalIdentities={[]}
          isLoading={false}
          onRemove={vi.fn()}
        />,
      );

      expect(
        screen.queryByText(/won.t fully disconnect this address/i),
      ).not.toBeInTheDocument();
    });

    it("shows no hint when the Email OTP address is the primary (not removable)", () => {
      render(
        <SignInMethodList
          emails={[makeEmail({ isPrimary: true })]}
          internalIdentities={[]}
          externalIdentities={[makeIdentity()]}
          isLoading={false}
          onUnlink={vi.fn()}
          onRemove={vi.fn()}
        />,
      );

      expect(
        screen.queryByText(/won.t fully disconnect this address/i),
      ).not.toBeInTheDocument();
    });
  });
});
