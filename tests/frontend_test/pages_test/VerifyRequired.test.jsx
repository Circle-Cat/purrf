import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import VerifyRequired from "@/pages/VerifyRequired";
import { useAuth } from "@/context/auth";
import { performGlobalLogout } from "@/utils/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

import "@testing-library/jest-dom/vitest";

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/utils/auth", () => ({
  performGlobalLogout: vi.fn(),
}));

// Surface the props the page wires into the shared form, plus a trigger to
// drive onVerified without exercising the OTP flow itself.
vi.mock("@/components/common/OtpVerifyForm", () => ({
  default: ({ initialEmail, idPrefix, onVerified, lockEmail }) => (
    <div
      data-testid="otp-form"
      data-initial-email={initialEmail}
      data-idprefix={idPrefix}
      data-lock-email={String(Boolean(lockEmail))}
    >
      <button onClick={() => onVerified({ ok: true })}>
        simulate verified
      </button>
    </div>
  ),
}));

const renderWall = () =>
  render(
    <MemoryRouter initialEntries={["/verify-required"]}>
      <Routes>
        <Route path="/verify-required" element={<VerifyRequired />} />
        <Route
          path={ROUTE_PATHS.PROFILE}
          element={<div>Mocked Profile Page</div>}
        />
      </Routes>
    </MemoryRouter>,
  );

describe("VerifyRequired", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      user: { email: "alice@gmail.com" },
      refreshAuth: vi.fn().mockResolvedValue(),
    });
  });

  afterEach(cleanup);

  it("renders the hard-wall heading and description", () => {
    renderWall();

    expect(
      screen.getByText("Verify your email to continue"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/We need a confirmed contact email/),
    ).toBeInTheDocument();
    expect(screen.getByTestId("otp-form")).toHaveAttribute(
      "data-lock-email",
      "false",
    );
  });

  it("renders the needs-link variant with a locked email", () => {
    useAuth.mockReturnValue({
      user: { email: "alice@gmail.com" },
      needsLink: true,
      refreshAuth: vi.fn().mockResolvedValue(),
    });

    renderWall();

    expect(
      screen.getByText("Link this sign-in to your account"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/An account already exists for this email/),
    ).toBeInTheDocument();
    expect(screen.getByTestId("otp-form")).toHaveAttribute(
      "data-lock-email",
      "true",
    );
  });

  it.each(["bob@circlecat.org", "Bob@CircleCat.org"])(
    "shows the internal-user hint when the sign-in email is %s",
    (email) => {
      useAuth.mockReturnValue({
        user: { email },
        refreshAuth: vi.fn().mockResolvedValue(),
      });

      renderWall();

      expect(
        screen.getByText(/verify your Google Workspace email/),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/please contact your manager/),
      ).toBeInTheDocument();
      // Hint only — the address field stays editable.
      expect(screen.getByTestId("otp-form")).toHaveAttribute(
        "data-lock-email",
        "false",
      );
    },
  );

  // @u.circlecat.org is the Microsoft domain; the hint names Google
  // Workspace specifically, so those sign-ins keep the generic copy.
  it.each(["alice@gmail.com", "bob@u.circlecat.org"])(
    "keeps the generic description for %s",
    (email) => {
      useAuth.mockReturnValue({
        user: { email },
        refreshAuth: vi.fn().mockResolvedValue(),
      });

      renderWall();

      expect(
        screen.getByText(/We need a confirmed contact email/),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/please contact your manager/),
      ).not.toBeInTheDocument();
    },
  );

  it("keeps the needs-link copy even for a company email", () => {
    useAuth.mockReturnValue({
      user: { email: "bob@circlecat.org" },
      needsLink: true,
      refreshAuth: vi.fn().mockResolvedValue(),
    });

    renderWall();

    expect(
      screen.getByText(/An account already exists for this email/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/please contact your manager/),
    ).not.toBeInTheDocument();
  });

  it("prefills the form with the user's email and the verify id prefix", () => {
    renderWall();

    const form = screen.getByTestId("otp-form");
    expect(form).toHaveAttribute("data-initial-email", "alice@gmail.com");
    expect(form).toHaveAttribute("data-idprefix", "verify");
  });

  it("falls back to an empty initial email when the user has none", () => {
    useAuth.mockReturnValue({ user: null, refreshAuth: vi.fn() });

    renderWall();

    expect(screen.getByTestId("otp-form")).toHaveAttribute(
      "data-initial-email",
      "",
    );
  });

  it("refreshes auth and navigates to the profile after verifying", async () => {
    const user = userEvent.setup();
    const refreshAuth = vi.fn().mockResolvedValue();
    useAuth.mockReturnValue({
      user: { email: "alice@gmail.com" },
      refreshAuth,
    });

    renderWall();

    await user.click(screen.getByRole("button", { name: "simulate verified" }));

    await waitFor(() =>
      expect(screen.getByText("Mocked Profile Page")).toBeInTheDocument(),
    );
    expect(refreshAuth).toHaveBeenCalledTimes(1);
  });

  it("logs out when the escape hatch is clicked", async () => {
    const user = userEvent.setup();
    renderWall();

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(performGlobalLogout).toHaveBeenCalledTimes(1);
  });
});
