import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import AddEmailDialog from "@/pages/SignInSecurity/components/AddEmailDialog";
import { addContactEmail } from "@/api/emailApi";

import "@testing-library/jest-dom/vitest";

vi.mock("@/api/emailApi", () => ({
  addContactEmail: vi.fn(),
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
      screen.getByText(/verify it before you can use it to sign in/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
  });

  it("does not render content when closed", () => {
    render(
      <AddEmailDialog open={false} onOpenChange={vi.fn()} onAdded={vi.fn()} />,
    );

    expect(screen.queryByText("Add an email")).not.toBeInTheDocument();
  });

  it("submits the address, toasts, closes and calls onAdded", async () => {
    addContactEmail.mockResolvedValue({ data: { ok: true } });
    const onOpenChange = vi.fn();
    const onAdded = vi.fn();
    const user = userEvent.setup();
    render(
      <AddEmailDialog open onOpenChange={onOpenChange} onAdded={onAdded} />,
    );

    await user.type(screen.getByLabelText("Email address"), "backup@x.com");
    await user.click(screen.getByRole("button", { name: "Add email" }));

    await waitFor(() =>
      expect(addContactEmail).toHaveBeenCalledWith("backup@x.com"),
    );
    expect(toast.success).toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onAdded).toHaveBeenCalledTimes(1);
  });

  it("toasts the backend message and stays open on failure", async () => {
    addContactEmail.mockRejectedValue({
      response: {
        data: { message: "Email already verified by another account" },
      },
    });
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(
      <AddEmailDialog open onOpenChange={onOpenChange} onAdded={vi.fn()} />,
    );

    await user.type(screen.getByLabelText("Email address"), "taken@x.com");
    await user.click(screen.getByRole("button", { name: "Add email" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Email already verified by another account",
      ),
    );
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("refuses to submit an empty address", async () => {
    const user = userEvent.setup();
    render(<AddEmailDialog open onOpenChange={vi.fn()} onAdded={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Add email" }));

    expect(addContactEmail).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });
});
