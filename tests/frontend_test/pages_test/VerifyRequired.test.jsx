import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { toast } from "sonner";

import VerifyRequired from "@/pages/VerifyRequired";
import { useAuth } from "@/context/auth";
import { performGlobalLogout } from "@/utils/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { initiateEmailVerification, verifyEmailOtp } from "@/api/emailApi";

import "@testing-library/jest-dom/vitest";

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/utils/auth", () => ({
  performGlobalLogout: vi.fn(),
}));

vi.mock("@/api/emailApi", () => ({
  initiateEmailVerification: vi.fn(),
  verifyEmailOtp: vi.fn(),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

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

// Advance the wall to the code step by sending a code for the prefilled email.
const advanceToCodeStep = async (user) => {
  initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });
  await user.click(screen.getByRole("button", { name: "Send code" }));
  await screen.findByLabelText("Enter the code sent to alice@gmail.com");
};

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
  });

  it("prefills the email field with the signed-in user's email", () => {
    renderWall();

    expect(screen.getByLabelText("Email address")).toHaveValue(
      "alice@gmail.com",
    );
  });

  it("warns and does not call the API when the email is blank", async () => {
    const user = userEvent.setup();
    useAuth.mockReturnValue({ user: null, refreshAuth: vi.fn() });
    renderWall();

    await user.click(screen.getByRole("button", { name: "Send code" }));

    expect(toast.error).toHaveBeenCalledWith("Enter an email address first.");
    expect(initiateEmailVerification).not.toHaveBeenCalled();
  });

  it("sends a code, advances to the code step, and toasts success", async () => {
    const user = userEvent.setup();
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });
    renderWall();

    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(initiateEmailVerification).toHaveBeenCalledWith("alice@gmail.com"),
    );
    expect(toast.success).toHaveBeenCalledWith(
      "We sent a 6-digit code to alice@gmail.com.",
    );
    expect(
      screen.getByLabelText("Enter the code sent to alice@gmail.com"),
    ).toBeInTheDocument();
  });

  it("keeps the user on the email step and toasts the error when sending fails", async () => {
    const user = userEvent.setup();
    initiateEmailVerification.mockRejectedValue({
      response: { data: { message: "Rate limited" } },
    });
    renderWall();

    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Rate limited"),
    );
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
  });

  it("warns and does not verify when the code is blank", async () => {
    const user = userEvent.setup();
    renderWall();
    await advanceToCodeStep(user);

    await user.click(screen.getByRole("button", { name: "Verify" }));

    expect(toast.error).toHaveBeenCalledWith("Enter the code from your email.");
    expect(verifyEmailOtp).not.toHaveBeenCalled();
  });

  it("verifies the code, refreshes auth, and navigates to the profile", async () => {
    const user = userEvent.setup();
    const refreshAuth = vi.fn().mockResolvedValue();
    useAuth.mockReturnValue({
      user: { email: "alice@gmail.com" },
      refreshAuth,
    });
    verifyEmailOtp.mockResolvedValue({ data: { ok: true } });
    renderWall();
    await advanceToCodeStep(user);

    await user.type(
      screen.getByLabelText("Enter the code sent to alice@gmail.com"),
      "  123456  ",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() =>
      expect(verifyEmailOtp).toHaveBeenCalledWith("st-1", "123456"),
    );
    expect(refreshAuth).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.getByText("Mocked Profile Page")).toBeInTheDocument(),
    );
  });

  it("toasts the error and stays on the code step when verification fails", async () => {
    const user = userEvent.setup();
    verifyEmailOtp.mockRejectedValue({
      response: { data: { message: "Bad code" } },
    });
    renderWall();
    await advanceToCodeStep(user);

    await user.type(
      screen.getByLabelText("Enter the code sent to alice@gmail.com"),
      "000000",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Bad code"));
    expect(
      screen.getByLabelText("Enter the code sent to alice@gmail.com"),
    ).toBeInTheDocument();
  });

  it("returns to the email step via 'Use a different email'", async () => {
    const user = userEvent.setup();
    renderWall();
    await advanceToCodeStep(user);

    await user.click(
      screen.getByRole("button", { name: "Use a different email" }),
    );

    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send code" }),
    ).toBeInTheDocument();
  });

  it("resends the code from the code step", async () => {
    const user = userEvent.setup();
    renderWall();
    await advanceToCodeStep(user);
    expect(initiateEmailVerification).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Resend code" }));

    await waitFor(() =>
      expect(initiateEmailVerification).toHaveBeenCalledTimes(2),
    );
  });

  it("logs out when the escape hatch is clicked", async () => {
    const user = userEvent.setup();
    renderWall();

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(performGlobalLogout).toHaveBeenCalledTimes(1);
  });
});
