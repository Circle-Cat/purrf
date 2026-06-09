import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import AddSignInMethodDialog from "@/pages/SignInSecurity/components/AddSignInMethodDialog";

import "@testing-library/jest-dom/vitest";

// Stand in for the real OTP form: expose a button that drives onVerified so we
// can test the dialog's post-verify behavior in isolation.
vi.mock("@/components/common/OtpVerifyForm", () => ({
  default: ({ onVerified, idPrefix }) => (
    <button
      data-testid="otp-form"
      data-idprefix={idPrefix}
      onClick={() => onVerified({ ok: true })}
    >
      simulate verified
    </button>
  ),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});

describe("AddSignInMethodDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("renders the title, description and OTP form when open", () => {
    render(
      <AddSignInMethodDialog open onOpenChange={vi.fn()} onAdded={vi.fn()} />,
    );

    expect(screen.getByText("Add a sign-in method")).toBeInTheDocument();
    expect(
      screen.getByText(/Verify an email address to use it for signing in/),
    ).toBeInTheDocument();
    expect(screen.getByTestId("otp-form")).toHaveAttribute(
      "data-idprefix",
      "add-signin",
    );
  });

  it("does not render content when closed", () => {
    render(
      <AddSignInMethodDialog
        open={false}
        onOpenChange={vi.fn()}
        onAdded={vi.fn()}
      />,
    );

    expect(screen.queryByText("Add a sign-in method")).not.toBeInTheDocument();
  });

  it("closes, toasts success, and calls onAdded after a verified add", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onAdded = vi.fn().mockResolvedValue();

    render(
      <AddSignInMethodDialog
        open
        onOpenChange={onOpenChange}
        onAdded={onAdded}
      />,
    );

    await user.click(screen.getByTestId("otp-form"));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(toast.success).toHaveBeenCalledWith("Sign-in method added.");
    await waitFor(() => expect(onAdded).toHaveBeenCalledTimes(1));
  });

  it("does not throw when onAdded is omitted", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    render(<AddSignInMethodDialog open onOpenChange={onOpenChange} />);

    await user.click(screen.getByTestId("otp-form"));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(toast.success).toHaveBeenCalledWith("Sign-in method added.");
  });
});
