import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import OtpVerifyForm from "@/components/common/OtpVerifyForm";
import { initiateEmailVerification, verifyEmailOtp } from "@/api/emailApi";

import "@testing-library/jest-dom/vitest";

vi.mock("@/api/emailApi", () => ({
  initiateEmailVerification: vi.fn(),
  verifyEmailOtp: vi.fn(),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

describe("OtpVerifyForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("renders the email step first, prefilled with initialEmail", () => {
    render(
      <OtpVerifyForm initialEmail="alice@gmail.com" onVerified={vi.fn()} />,
    );

    expect(screen.getByLabelText("Email address")).toHaveValue(
      "alice@gmail.com",
    );
    expect(
      screen.getByRole("button", { name: "Send code" }),
    ).toBeInTheDocument();
  });

  it("hints at the spam folder only once a code has been sent", async () => {
    const user = userEvent.setup();
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });
    render(<OtpVerifyForm initialEmail="bob@gmail.com" onVerified={vi.fn()} />);

    // Nothing has been mailed yet, so the hint would be noise on the email step.
    expect(screen.queryByText(/spam folder/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Send code" }));

    expect(
      await screen.findByText(/Check your spam folder or resend it/i),
    ).toBeInTheDocument();
  });

  it("warns and does not call the API when the email is blank", async () => {
    const user = userEvent.setup();
    render(<OtpVerifyForm onVerified={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Send code" }));

    expect(toast.error).toHaveBeenCalledWith(
      "Please enter your email address.",
    );
    expect(initiateEmailVerification).not.toHaveBeenCalled();
  });

  it("sends a code, advances to the code step, and toasts success", async () => {
    const user = userEvent.setup();
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });

    render(<OtpVerifyForm onVerified={vi.fn()} />);

    await user.type(screen.getByLabelText("Email address"), "bob@gmail.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(initiateEmailVerification).toHaveBeenCalledWith("bob@gmail.com"),
    );
    expect(toast.success).toHaveBeenCalledWith(
      "Verification code sent to bob@gmail.com.",
    );
    expect(
      screen.getByLabelText("Enter the 6-digit code sent to bob@gmail.com"),
    ).toBeInTheDocument();
  });

  it("trims the email before sending", async () => {
    const user = userEvent.setup();
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });

    render(<OtpVerifyForm onVerified={vi.fn()} />);

    await user.type(
      screen.getByLabelText("Email address"),
      "  bob@gmail.com  ",
    );
    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(initiateEmailVerification).toHaveBeenCalledWith("bob@gmail.com"),
    );
  });

  it("shows the server error and stays on the email step when sending fails", async () => {
    const user = userEvent.setup();
    initiateEmailVerification.mockRejectedValue({
      response: { data: { message: "Rate limited" } },
    });

    render(<OtpVerifyForm onVerified={vi.fn()} />);

    await user.type(screen.getByLabelText("Email address"), "bob@gmail.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Rate limited"),
    );
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
  });

  it("falls back to a generic error message when the failure has no message", async () => {
    const user = userEvent.setup();
    initiateEmailVerification.mockRejectedValue(new Error("boom"));

    render(<OtpVerifyForm onVerified={vi.fn()} />);

    await user.type(screen.getByLabelText("Email address"), "bob@gmail.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Something went wrong. Please try again.",
      ),
    );
  });

  const advanceToCodeStep = async (user) => {
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });
    await user.type(screen.getByLabelText("Email address"), "bob@gmail.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByLabelText(
      "Enter the 6-digit code sent to bob@gmail.com",
    );
  };

  it("warns and does not verify when the code is blank", async () => {
    const user = userEvent.setup();
    render(<OtpVerifyForm onVerified={vi.fn()} />);
    await advanceToCodeStep(user);

    await user.click(screen.getByRole("button", { name: "Verify" }));

    expect(toast.error).toHaveBeenCalledWith(
      "Please enter the 6-digit verification code.",
    );
    expect(verifyEmailOtp).not.toHaveBeenCalled();
  });

  it("verifies the trimmed code and invokes onVerified with the result", async () => {
    const user = userEvent.setup();
    const onVerified = vi.fn();
    verifyEmailOtp.mockResolvedValue({
      data: { ok: true, email: "bob@gmail.com" },
    });

    render(<OtpVerifyForm onVerified={onVerified} />);
    await advanceToCodeStep(user);

    await user.type(
      screen.getByLabelText("Enter the 6-digit code sent to bob@gmail.com"),
      "  123456  ",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() =>
      expect(verifyEmailOtp).toHaveBeenCalledWith("st-1", "123456"),
    );
    expect(onVerified).toHaveBeenCalledWith({
      ok: true,
      email: "bob@gmail.com",
    });
  });

  it("shows the server error when verifying fails", async () => {
    const user = userEvent.setup();
    const onVerified = vi.fn();
    verifyEmailOtp.mockRejectedValue({
      response: { data: { message: "Bad code" } },
    });

    render(<OtpVerifyForm onVerified={onVerified} />);
    await advanceToCodeStep(user);

    await user.type(
      screen.getByLabelText("Enter the 6-digit code sent to bob@gmail.com"),
      "000000",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Bad code"));
    expect(onVerified).not.toHaveBeenCalled();
  });

  it("returns to the email step via 'Change email'", async () => {
    const user = userEvent.setup();
    render(<OtpVerifyForm onVerified={vi.fn()} />);
    await advanceToCodeStep(user);

    await user.click(screen.getByRole("button", { name: "Change email" }));

    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send code" }),
    ).toBeInTheDocument();
  });

  it("resends the code from the code step", async () => {
    const user = userEvent.setup();
    render(<OtpVerifyForm onVerified={vi.fn()} />);
    await advanceToCodeStep(user);

    expect(initiateEmailVerification).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Resend code" }));

    await waitFor(() =>
      expect(initiateEmailVerification).toHaveBeenCalledTimes(2),
    );
  });

  it("uses the custom idPrefix for input ids", () => {
    render(<OtpVerifyForm onVerified={vi.fn()} idPrefix="add-signin" />);

    expect(screen.getByLabelText("Email address")).toHaveAttribute(
      "id",
      "add-signin-email",
    );
  });
});
