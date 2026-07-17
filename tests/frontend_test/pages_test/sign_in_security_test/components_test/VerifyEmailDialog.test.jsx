import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import VerifyEmailDialog from "@/pages/SignInSecurity/components/VerifyEmailDialog";

import "@testing-library/jest-dom/vitest";

// Stand in for the real OTP form: expose the locked address and a button that
// drives onVerified so we can test the dialog's post-verify behavior.
vi.mock("@/components/common/OtpVerifyForm", () => ({
  default: ({ onVerified, idPrefix, initialEmail, lockEmail }) => (
    <button
      data-testid="otp-form"
      data-idprefix={idPrefix}
      data-email={initialEmail}
      data-locked={lockEmail ? "yes" : "no"}
      onClick={() => onVerified({ ok: true })}
    >
      simulate verified
    </button>
  ),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});

describe("VerifyEmailDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("renders the OTP form locked to the target address when open", () => {
    render(
      <VerifyEmailDialog
        open
        onOpenChange={vi.fn()}
        email="backup@x.com"
        onVerified={vi.fn()}
      />,
    );

    expect(screen.getByText("Verify email")).toBeInTheDocument();
    const form = screen.getByTestId("otp-form");
    expect(form).toHaveAttribute("data-email", "backup@x.com");
    expect(form).toHaveAttribute("data-locked", "yes");
  });

  it("does not render content when closed", () => {
    render(
      <VerifyEmailDialog
        open={false}
        onOpenChange={vi.fn()}
        email="backup@x.com"
        onVerified={vi.fn()}
      />,
    );

    expect(screen.queryByText("Verify email")).not.toBeInTheDocument();
  });

  it("closes, toasts success, and calls onVerified after a verified code", async () => {
    const onOpenChange = vi.fn();
    const onVerified = vi.fn();
    const user = userEvent.setup();
    render(
      <VerifyEmailDialog
        open
        onOpenChange={onOpenChange}
        email="backup@x.com"
        onVerified={onVerified}
      />,
    );

    await user.click(screen.getByTestId("otp-form"));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(toast.success).toHaveBeenCalled();
    expect(onVerified).toHaveBeenCalledTimes(1);
  });
});
