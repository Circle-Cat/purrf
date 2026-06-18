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

  it("shows an empty-state message when there are no identities", () => {
    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={[]}
        isLoading={false}
      />,
    );

    expect(screen.getByText("No sign-in methods yet.")).toBeInTheDocument();
  });

  it("renders the internal identity first and tags it Internal", () => {
    const internalIdentity = makeIdentity({
      identityId: 99,
      subjectIdentifier: "auth0|work",
      emailClaim: "alice@circlecat.org",
    });

    render(
      <SignInMethodList
        internalIdentities={[internalIdentity]}
        externalIdentities={[]}
        isLoading={false}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getByText("Internal")).toBeInTheDocument();
    expect(
      within(rows[0]).getByText("alice@circlecat.org"),
    ).toBeInTheDocument();
  });

  it("renders external identities without the Internal badge", () => {
    const externalIdentities = [
      makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
      makeIdentity({ identityId: 2, subjectIdentifier: "auth0|2" }),
    ];

    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={externalIdentities}
        isLoading={false}
      />,
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.queryByText("Internal")).not.toBeInTheDocument();
  });

  it("lists the internal identity ahead of external identities", () => {
    const internalIdentity = makeIdentity({
      identityId: 99,
      subjectIdentifier: "auth0|work",
      emailClaim: "work@circlecat.org",
    });
    const externalIdentities = [
      makeIdentity({
        identityId: 1,
        subjectIdentifier: "google-oauth2|1",
        emailClaim: "personal@gmail.com",
      }),
    ];

    render(
      <SignInMethodList
        internalIdentities={[internalIdentity]}
        externalIdentities={externalIdentities}
        isLoading={false}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Internal")).toBeInTheDocument();
    expect(within(rows[0]).getByText("work@circlecat.org")).toBeInTheDocument();
    expect(within(rows[1]).getByText("personal@gmail.com")).toBeInTheDocument();
  });

  it("renders every internal identity, each tagged Internal, ahead of external ones", () => {
    const internalIdentities = [
      makeIdentity({
        identityId: 2,
        subjectIdentifier: "google-oauth2|sso",
        emailClaim: "alice@circlecat.org",
      }),
      makeIdentity({
        identityId: 193,
        subjectIdentifier: "email|otp",
        emailClaim: "alice@circlecat.org",
      }),
    ];
    const externalIdentities = [
      makeIdentity({
        identityId: 1,
        subjectIdentifier: "google-oauth2|1",
        emailClaim: "personal@gmail.com",
      }),
    ];

    render(
      <SignInMethodList
        internalIdentities={internalIdentities}
        externalIdentities={externalIdentities}
        isLoading={false}
        onUnlink={vi.fn()}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    // Both internal identities render up front, each badged Internal, and neither
    // offers Unlink (active employees keep their corp sign-ins).
    expect(within(rows[0]).getByText("Internal")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Internal")).toBeInTheDocument();
    expect(screen.getAllByText("Internal")).toHaveLength(2);
    expect(
      within(rows[0]).queryByRole("button", { name: "Unlink" }),
    ).not.toBeInTheDocument();
    expect(
      within(rows[1]).queryByRole("button", { name: "Unlink" }),
    ).not.toBeInTheDocument();
    expect(within(rows[2]).getByText("personal@gmail.com")).toBeInTheDocument();
  });

  it("maps known provider prefixes to human-friendly labels", () => {
    const externalIdentities = [
      makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
      makeIdentity({ identityId: 2, subjectIdentifier: "google|2" }),
      makeIdentity({ identityId: 3, subjectIdentifier: "email|3" }),
      makeIdentity({ identityId: 4, subjectIdentifier: "auth0|4" }),
    ];

    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={externalIdentities}
        isLoading={false}
      />,
    );

    expect(screen.getAllByText("Google")).toHaveLength(2);
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Email & password")).toBeInTheDocument();
  });

  it("falls back to the raw provider for unknown prefixes", () => {
    const externalIdentities = [
      makeIdentity({ identityId: 1, subjectIdentifier: "github|1" }),
    ];

    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={externalIdentities}
        isLoading={false}
      />,
    );

    expect(screen.getByText("github")).toBeInTheDocument();
  });

  it("labels an empty or malformed subject identifier as Unknown", () => {
    const externalIdentities = [
      makeIdentity({ identityId: 1, subjectIdentifier: "" }),
    ];

    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={externalIdentities}
        isLoading={false}
      />,
    );

    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("omits the email claim text when it is missing", () => {
    const externalIdentities = [
      makeIdentity({
        identityId: 1,
        subjectIdentifier: "google-oauth2|1",
        emailClaim: null,
      }),
    ];

    render(
      <SignInMethodList
        internalIdentities={[]}
        externalIdentities={externalIdentities}
        isLoading={false}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getByText("Google")).toBeInTheDocument();
    // Only the provider label is present, no email claim line.
    expect(within(rows[0]).queryByText(/@/)).not.toBeInTheDocument();
  });

  describe("Unlink action", () => {
    it("never offers Unlink for the internal identity", () => {
      const internalIdentity = makeIdentity({
        identityId: 99,
        subjectIdentifier: "auth0|work",
      });
      const externalIdentities = [
        makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[internalIdentity]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      // Internal row (first) has no Unlink; the external one does (total > 1).
      expect(
        within(rows[0]).queryByRole("button", { name: "Unlink" }),
      ).not.toBeInTheDocument();
      expect(
        within(rows[1]).getByRole("button", { name: "Unlink" }),
      ).toBeInTheDocument();
    });

    it("does not offer Unlink when only one sign-in method remains", () => {
      const externalIdentities = [
        makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(
        screen.queryByRole("button", { name: "Unlink" }),
      ).not.toBeInTheDocument();
    });

    it("offers Unlink on every external identity when more than one exists", () => {
      const externalIdentities = [
        makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
        makeIdentity({ identityId: 2, subjectIdentifier: "auth0|2" }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(screen.getAllByRole("button", { name: "Unlink" })).toHaveLength(2);
    });

    it("calls onUnlink with the identity when clicked", async () => {
      const user = userEvent.setup();
      const onUnlink = vi.fn().mockResolvedValue();
      const externalIdentities = [
        makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
        makeIdentity({ identityId: 2, subjectIdentifier: "auth0|2" }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={onUnlink}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      await user.click(within(rows[1]).getByRole("button", { name: "Unlink" }));

      expect(onUnlink).toHaveBeenCalledWith(externalIdentities[1]);
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
      const externalIdentities = [
        makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
        makeIdentity({ identityId: 2, subjectIdentifier: "auth0|2" }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={onUnlink}
        />,
      );

      const [firstButton] = screen.getAllByRole("button", { name: "Unlink" });
      await user.click(firstButton);

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

  describe("Current session identity", () => {
    it("badges the current-session identity as the primary sign-in", () => {
      const externalIdentities = [
        makeIdentity({
          identityId: 1,
          subjectIdentifier: "google-oauth2|1",
          isCurrentSession: true,
        }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(screen.getByText("Primary sign-in")).toBeInTheDocument();
    });

    it("does not badge identities that are not the current session", () => {
      const externalIdentities = [
        makeIdentity({
          identityId: 1,
          subjectIdentifier: "google-oauth2|1",
          isCurrentSession: false,
        }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      expect(screen.queryByText("Primary sign-in")).not.toBeInTheDocument();
    });

    it("hides Unlink for the current-session identity while peers keep theirs", () => {
      const externalIdentities = [
        makeIdentity({
          identityId: 1,
          subjectIdentifier: "google-oauth2|1",
          isCurrentSession: true,
        }),
        makeIdentity({
          identityId: 2,
          subjectIdentifier: "auth0|2",
          isCurrentSession: false,
        }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      // total > 1 so canUnlink is true, but the current-session row still has
      // no Unlink control; the other external identity keeps its own.
      expect(
        within(rows[0]).queryByRole("button", { name: "Unlink" }),
      ).not.toBeInTheDocument();
      expect(
        within(rows[1]).getByRole("button", { name: "Unlink" }),
      ).toBeInTheDocument();
    });

    it("shows both Internal and Primary sign-in badges on an internal current-session identity", () => {
      const internalIdentity = makeIdentity({
        identityId: 99,
        subjectIdentifier: "auth0|work",
        isCurrentSession: true,
      });
      const externalIdentities = [
        makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
      ];

      render(
        <SignInMethodList
          internalIdentities={[internalIdentity]}
          externalIdentities={externalIdentities}
          isLoading={false}
          onUnlink={vi.fn()}
        />,
      );

      const rows = screen.getAllByRole("listitem");
      expect(within(rows[0]).getByText("Internal")).toBeInTheDocument();
      expect(within(rows[0]).getByText("Primary sign-in")).toBeInTheDocument();
      expect(
        within(rows[0]).queryByRole("button", { name: "Unlink" }),
      ).not.toBeInTheDocument();
    });
  });
});
