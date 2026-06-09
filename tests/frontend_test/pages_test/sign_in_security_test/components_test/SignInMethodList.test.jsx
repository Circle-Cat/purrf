import { render, screen, cleanup, within } from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";

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
        internalIdentity={null}
        externalIdentities={[]}
        isLoading
      />,
    );

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no identities", () => {
    render(
      <SignInMethodList
        internalIdentity={null}
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
        internalIdentity={internalIdentity}
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
        internalIdentity={null}
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
        internalIdentity={internalIdentity}
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

  it("maps known provider prefixes to human-friendly labels", () => {
    const externalIdentities = [
      makeIdentity({ identityId: 1, subjectIdentifier: "google-oauth2|1" }),
      makeIdentity({ identityId: 2, subjectIdentifier: "google|2" }),
      makeIdentity({ identityId: 3, subjectIdentifier: "email|3" }),
      makeIdentity({ identityId: 4, subjectIdentifier: "auth0|4" }),
    ];

    render(
      <SignInMethodList
        internalIdentity={null}
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
        internalIdentity={null}
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
        internalIdentity={null}
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
        internalIdentity={null}
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
});
