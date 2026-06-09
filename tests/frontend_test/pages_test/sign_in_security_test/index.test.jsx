import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import SignInSecurity from "@/pages/SignInSecurity";
import { useEmailSettings } from "@/pages/SignInSecurity/hooks/useEmailSettings";

import "@testing-library/jest-dom/vitest";

vi.mock("@/pages/SignInSecurity/hooks/useEmailSettings", () => ({
  useEmailSettings: vi.fn(),
}));

vi.mock("@/pages/SignInSecurity/components/EmailAddressList", () => ({
  default: ({ emails, isLoading }) => (
    <div data-testid="email-address-list">
      EmailAddressList:{isLoading ? "loading" : "ready"}:{emails.length}
    </div>
  ),
}));

vi.mock("@/pages/SignInSecurity/components/SignInMethodList", () => ({
  default: ({ internalIdentity, externalIdentities, isLoading }) => (
    <div data-testid="sign-in-method-list">
      SignInMethodList:{isLoading ? "loading" : "ready"}:
      {internalIdentity ? "internal" : "none"}:{externalIdentities.length}
    </div>
  ),
}));

describe("SignInSecurity page", () => {
  const defaultHookValue = {
    isLoading: false,
    emails: [],
    internalIdentity: null,
    externalIdentities: [],
    refresh: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useEmailSettings.mockReturnValue(defaultHookValue);
  });

  afterEach(cleanup);

  it("renders both section cards with titles and descriptions", () => {
    render(<SignInSecurity />);

    expect(screen.getByText("Email addresses")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your contact email addresses. Your primary address receives account notifications.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Sign-in methods")).toBeInTheDocument();
    expect(
      screen.getByText("The accounts you can use to sign in to Purrf."),
    ).toBeInTheDocument();
  });

  it("renders both child lists", () => {
    render(<SignInSecurity />);

    expect(screen.getByTestId("email-address-list")).toBeInTheDocument();
    expect(screen.getByTestId("sign-in-method-list")).toBeInTheDocument();
  });

  it("passes hook data through to the child lists", () => {
    useEmailSettings.mockReturnValue({
      ...defaultHookValue,
      isLoading: false,
      emails: [{ emailId: 1 }, { emailId: 2 }],
      internalIdentity: { identityId: 9 },
      externalIdentities: [{ identityId: 1 }],
    });

    render(<SignInSecurity />);

    expect(screen.getByTestId("email-address-list")).toHaveTextContent(
      "EmailAddressList:ready:2",
    );
    expect(screen.getByTestId("sign-in-method-list")).toHaveTextContent(
      "SignInMethodList:ready:internal:1",
    );
  });

  it("propagates the loading state to both child lists", () => {
    useEmailSettings.mockReturnValue({
      ...defaultHookValue,
      isLoading: true,
    });

    render(<SignInSecurity />);

    expect(screen.getByTestId("email-address-list")).toHaveTextContent(
      "loading",
    );
    expect(screen.getByTestId("sign-in-method-list")).toHaveTextContent(
      "loading",
    );
  });
});
