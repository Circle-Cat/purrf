import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import StepUpConfirmDialog from "@/pages/SignInSecurity/components/StepUpConfirmDialog";

import "@testing-library/jest-dom/vitest";

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

const baseProps = {
  open: true,
  onOpenChange: vi.fn(),
  title: "Switch primary email",
  description: "Enter the code we sent you.",
  confirmLabel: "Switch primary",
  onConfirm: vi.fn(),
};

const renderDialog = (props = {}) =>
  render(<StepUpConfirmDialog {...baseProps} {...props} />);

describe("StepUpConfirmDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("renders the title, description and confirm label when open", () => {
    renderDialog();

    expect(screen.getByText("Switch primary email")).toBeInTheDocument();
    expect(screen.getByText("Enter the code we sent you.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Switch primary" }),
    ).toBeInTheDocument();
  });

  it("does not render dialog content when closed", () => {
    renderDialog({ open: false });

    expect(screen.queryByText("Switch primary email")).not.toBeInTheDocument();
  });

  it("warns and does not confirm when the code is blank", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });

    await user.click(screen.getByRole("button", { name: "Switch primary" }));

    expect(toast.error).toHaveBeenCalledWith("Enter the code from your email.");
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("calls onConfirm with the trimmed code", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue();
    renderDialog({ onConfirm });

    await user.type(screen.getByLabelText("Verification code"), "  123456  ");
    await user.click(screen.getByRole("button", { name: "Switch primary" }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith("123456"));
  });

  it("hides the resend link when onResend is not provided", () => {
    renderDialog({ onResend: undefined });

    expect(
      screen.queryByRole("button", { name: "Resend code" }),
    ).not.toBeInTheDocument();
  });

  it("resends the code and toasts success when onResend resolves", async () => {
    const user = userEvent.setup();
    const onResend = vi.fn().mockResolvedValue();
    renderDialog({ onResend });

    await user.click(screen.getByRole("button", { name: "Resend code" }));

    await waitFor(() => expect(onResend).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith(
      "We sent a new code to your primary email.",
    );
  });

  it("clears the entered code after a successful resend", async () => {
    const user = userEvent.setup();
    const onResend = vi.fn().mockResolvedValue();
    renderDialog({ onResend });

    const input = screen.getByLabelText("Verification code");
    await user.type(input, "999999");
    await user.click(screen.getByRole("button", { name: "Resend code" }));

    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("shows the server error when resend fails", async () => {
    const user = userEvent.setup();
    const onResend = vi
      .fn()
      .mockRejectedValue({ response: { data: { message: "Too soon" } } });
    renderDialog({ onResend });

    await user.click(screen.getByRole("button", { name: "Resend code" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Too soon"));
  });

  it("shows a generic error when resend fails without a message", async () => {
    const user = userEvent.setup();
    const onResend = vi.fn().mockRejectedValue(new Error("boom"));
    renderDialog({ onResend });

    await user.click(screen.getByRole("button", { name: "Resend code" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Could not resend the code. Please try again.",
      ),
    );
  });

  it("renders the confirm button with the destructive variant label intact", () => {
    renderDialog({
      confirmLabel: "Remove sign-in method",
      confirmVariant: "destructive",
    });

    expect(
      screen.getByRole("button", { name: "Remove sign-in method" }),
    ).toBeInTheDocument();
  });

  it("resets the code field when reopened", async () => {
    const user = userEvent.setup();
    const { rerender } = renderDialog();

    const input = screen.getByLabelText("Verification code");
    await user.type(input, "555555");
    expect(input).toHaveValue("555555");

    rerender(<StepUpConfirmDialog {...baseProps} open={false} />);
    rerender(<StepUpConfirmDialog {...baseProps} open={true} />);

    expect(screen.getByLabelText("Verification code")).toHaveValue("");
  });
});
