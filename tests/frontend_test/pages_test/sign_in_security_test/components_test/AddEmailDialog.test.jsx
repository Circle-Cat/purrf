import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import AddEmailDialog from "@/pages/SignInSecurity/components/AddEmailDialog";
import { initiateEmailVerification, verifyEmailOtp } from "@/api/emailApi";

import "@testing-library/jest-dom/vitest";

vi.mock("@/api/emailApi", () => ({
  initiateEmailVerification: vi.fn(),
  verifyEmailOtp: vi.fn(),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

describe("AddEmailDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("renders the title, description and address input when open", () => {
    render(<AddEmailDialog open onOpenChange={vi.fn()} onAdded={vi.fn()} />);

    expect(screen.getByText("Add an email")).toBeInTheDocument();
    expect(
      screen.getByText(/We'll send a verification code to the address/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
  });

  it("does not render content when closed", () => {
    render(
      <AddEmailDialog open={false} onOpenChange={vi.fn()} onAdded={vi.fn()} />,
    );

    expect(screen.queryByText("Add an email")).not.toBeInTheDocument();
  });

  it("initiates verification for the typed address and advances to the code step", async () => {
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });
    const user = userEvent.setup();
    render(<AddEmailDialog open onOpenChange={vi.fn()} onAdded={vi.fn()} />);

    await user.type(screen.getByLabelText("Email address"), "backup@x.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(initiateEmailVerification).toHaveBeenCalledWith("backup@x.com"),
    );
    expect(
      screen.getByLabelText("Enter the code sent to backup@x.com"),
    ).toBeInTheDocument();
  });

  it("verifies the code, toasts success, closes and calls onAdded", async () => {
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });
    verifyEmailOtp.mockResolvedValue({
      data: { ok: true, email: "backup@x.com" },
    });
    const onOpenChange = vi.fn();
    const onAdded = vi.fn();
    const user = userEvent.setup();
    render(
      <AddEmailDialog open onOpenChange={onOpenChange} onAdded={onAdded} />,
    );

    await user.type(screen.getByLabelText("Email address"), "backup@x.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByLabelText("Enter the code sent to backup@x.com");

    await user.type(
      screen.getByLabelText("Enter the code sent to backup@x.com"),
      "123456",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() =>
      expect(verifyEmailOtp).toHaveBeenCalledWith("st-1", "123456"),
    );
    expect(toast.success).toHaveBeenCalledWith("Email added and verified.");
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onAdded).toHaveBeenCalledTimes(1);
  });

  it("toasts the backend message and stays open when initiating fails", async () => {
    initiateEmailVerification.mockRejectedValue({
      response: {
        data: { message: "Email already verified by another account" },
      },
    });
    const onOpenChange = vi.fn();
    const onAdded = vi.fn();
    const user = userEvent.setup();
    render(
      <AddEmailDialog open onOpenChange={onOpenChange} onAdded={onAdded} />,
    );

    await user.type(screen.getByLabelText("Email address"), "taken@x.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Email already verified by another account",
      ),
    );
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(onAdded).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
  });

  it("resets to the email step on close and reopen", async () => {
    initiateEmailVerification.mockResolvedValue({ data: { state: "st-1" } });
    const user = userEvent.setup();
    const { rerender } = render(
      <AddEmailDialog open onOpenChange={vi.fn()} onAdded={vi.fn()} />,
    );

    await user.type(screen.getByLabelText("Email address"), "backup@x.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByLabelText("Enter the code sent to backup@x.com");

    rerender(
      <AddEmailDialog open={false} onOpenChange={vi.fn()} onAdded={vi.fn()} />,
    );
    rerender(
      <AddEmailDialog open onOpenChange={vi.fn()} onAdded={vi.fn()} />,
    );

    expect(screen.getByLabelText("Email address")).toHaveValue("");
    expect(
      screen.getByRole("button", { name: "Send code" }),
    ).toBeInTheDocument();
  });
});
