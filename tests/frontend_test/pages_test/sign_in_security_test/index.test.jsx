import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import SignInSecurity from "@/pages/SignInSecurity";
import { useEmailSettings } from "@/pages/SignInSecurity/hooks/useEmailSettings";
import {
  initiateSetPrimary,
  confirmSetPrimary,
  initiateUnlink,
  confirmUnlink,
  removeContactEmail,
} from "@/api/emailApi";

import "@testing-library/jest-dom/vitest";

vi.mock("@/pages/SignInSecurity/hooks/useEmailSettings", () => ({
  useEmailSettings: vi.fn(),
}));

vi.mock("@/api/emailApi", () => ({
  initiateSetPrimary: vi.fn(),
  confirmSetPrimary: vi.fn(),
  initiateUnlink: vi.fn(),
  confirmUnlink: vi.fn(),
  removeContactEmail: vi.fn(),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

// Child list mock exposes buttons that drive the page's action callbacks.
// The set-primary, unlink and verify actions are all triggered from this
// single merged list.
vi.mock("@/pages/SignInSecurity/components/SignInMethodList", () => ({
  default: ({
    emails,
    internalIdentities,
    externalIdentities,
    isLoading,
    onUnlink,
    onSetPrimary,
    onRemove,
  }) => (
    <div data-testid="sign-in-method-list">
      SignInMethodList:{isLoading ? "loading" : "ready"}:
      {internalIdentities.length ? "internal" : "none"}:
      {externalIdentities.length}:{emails.length}
      <button
        onClick={() => onSetPrimary({ emailId: 2, email: "bob@gmail.com" })}
      >
        trigger-set-primary
      </button>
      <button
        onClick={() =>
          onUnlink({
            identityId: 7,
            subjectIdentifier: "google-oauth2|7",
            emailClaim: "ext@gmail.com",
          })
        }
      >
        trigger-unlink
      </button>
      <button
        onClick={() =>
          onRemove({ emailId: 3, email: "backup@x.com", otpConfirmed: false })
        }
      >
        trigger-remove
      </button>
    </div>
  ),
}));

vi.mock("@/pages/SignInSecurity/components/AddEmailDialog", () => ({
  default: ({ open, onAdded }) =>
    open ? (
      <div data-testid="add-dialog">
        <button onClick={() => onAdded()}>add-onAdded</button>
      </div>
    ) : null,
}));

// One mock serves both StepUpConfirmDialog instances; buttons embed the title
// so the open one is unambiguous (only a single target is ever set at a time).
vi.mock("@/pages/SignInSecurity/components/StepUpConfirmDialog", () => ({
  default: ({ open, title, description, onConfirm, onResend, onOpenChange }) =>
    open ? (
      <div data-testid="stepup-dialog">
        <span data-testid="stepup-title">{title}</span>
        <span data-testid="stepup-desc">{description}</span>
        <button
          onClick={() => onConfirm("123456")}
        >{`confirm:${title}`}</button>
        <button onClick={() => onResend()}>{`resend:${title}`}</button>
        <button onClick={() => onOpenChange(false)}>{`close:${title}`}</button>
      </div>
    ) : null,
}));

const PRIMARY_TITLE = "Set primary contact email";
const UNLINK_TITLE = "Remove sign-in method";

describe("SignInSecurity page", () => {
  const refresh = vi.fn();
  const defaultHookValue = {
    isLoading: false,
    emails: [],
    internalIdentities: [],
    externalIdentities: [],
    refresh,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useEmailSettings.mockReturnValue(defaultHookValue);
  });

  afterEach(cleanup);

  it("renders a single card with the merged sign-in and email list", () => {
    render(<SignInSecurity />);

    expect(screen.getByText("Sign-in methods & emails")).toBeInTheDocument();
    expect(
      screen.getByText(/The methods you can use to sign in to Purrf\./),
    ).toBeInTheDocument();
    expect(screen.getByTestId("sign-in-method-list")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add email" }),
    ).toBeInTheDocument();
  });

  it("passes hook data (including emails) through to the sign-in method list", () => {
    useEmailSettings.mockReturnValue({
      ...defaultHookValue,
      emails: [{ emailId: 1 }, { emailId: 2 }],
      internalIdentities: [{ identityId: 9 }],
      externalIdentities: [{ identityId: 1 }],
    });

    render(<SignInSecurity />);

    expect(screen.getByTestId("sign-in-method-list")).toHaveTextContent(
      "SignInMethodList:ready:internal:1:2",
    );
  });

  it("propagates the loading state to the sign-in method list", () => {
    useEmailSettings.mockReturnValue({ ...defaultHookValue, isLoading: true });

    render(<SignInSecurity />);

    expect(screen.getByTestId("sign-in-method-list")).toHaveTextContent(
      "loading",
    );
  });

  it("keeps the step-up dialogs closed initially", () => {
    render(<SignInSecurity />);

    expect(screen.queryByTestId("stepup-dialog")).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-dialog")).not.toBeInTheDocument();
  });

  describe("Add email", () => {
    it("opens the add dialog and refreshes after an add", async () => {
      const user = userEvent.setup();
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "Add email" }));
      expect(screen.getByTestId("add-dialog")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "add-onAdded" }));
      expect(refresh).toHaveBeenCalledTimes(1);
    });
  });

  describe("Remove email", () => {
    it("removes the address, toasts success and refreshes", async () => {
      removeContactEmail.mockResolvedValue({ data: { ok: true } });
      const user = userEvent.setup();
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "trigger-remove" }));

      await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
      expect(removeContactEmail).toHaveBeenCalledWith(3);
      expect(toast.success).toHaveBeenCalledWith("Email removed.");
    });

    it("toasts the backend message when removal fails", async () => {
      removeContactEmail.mockRejectedValue({
        response: { data: { message: "Nope" } },
      });
      const user = userEvent.setup();
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "trigger-remove" }));

      await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Nope"));
      expect(refresh).not.toHaveBeenCalled();
    });
  });

  describe("Set primary contact email", () => {
    it("initiates the switch and opens the dialog with the target email", async () => {
      const user = userEvent.setup();
      initiateSetPrimary.mockResolvedValue({ data: { state: "st-1" } });
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "trigger-set-primary" }),
      );

      await waitFor(() => expect(initiateSetPrimary).toHaveBeenCalledWith(2));
      expect(screen.getByTestId("stepup-title")).toHaveTextContent(
        PRIMARY_TITLE,
      );
      expect(screen.getByTestId("stepup-desc")).toHaveTextContent(
        "bob@gmail.com",
      );
    });

    it("names the current primary address in the step-up description", async () => {
      useEmailSettings.mockReturnValue({
        ...defaultHookValue,
        emails: [
          {
            emailId: 9,
            email: "prime@x.com",
            otpConfirmed: true,
            isPrimary: true,
          },
        ],
      });
      const user = userEvent.setup();
      initiateSetPrimary.mockResolvedValue({ data: { state: "st-1" } });
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "trigger-set-primary" }),
      );

      await waitFor(() =>
        expect(screen.getByTestId("stepup-desc")).toHaveTextContent(
          "we sent to prime@x.com",
        ),
      );
    });

    it("toasts and stays closed when initiate fails", async () => {
      const user = userEvent.setup();
      initiateSetPrimary.mockRejectedValue({
        response: { data: { message: "Nope" } },
      });
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "trigger-set-primary" }),
      );

      await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Nope"));
      expect(screen.queryByTestId("stepup-dialog")).not.toBeInTheDocument();
    });

    it("confirms the switch, closes, toasts success and refreshes", async () => {
      const user = userEvent.setup();
      initiateSetPrimary.mockResolvedValue({ data: { state: "st-1" } });
      confirmSetPrimary.mockResolvedValue({ data: { ok: true } });
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "trigger-set-primary" }),
      );
      await screen.findByTestId("stepup-dialog");

      await user.click(
        screen.getByRole("button", { name: `confirm:${PRIMARY_TITLE}` }),
      );

      await waitFor(() =>
        expect(confirmSetPrimary).toHaveBeenCalledWith(2, "st-1", "123456"),
      );
      expect(toast.success).toHaveBeenCalledWith(
        "Primary contact email updated.",
      );
      expect(refresh).toHaveBeenCalledTimes(1);
      await waitFor(() =>
        expect(screen.queryByTestId("stepup-dialog")).not.toBeInTheDocument(),
      );
    });

    it("toasts and keeps the dialog open when confirm fails", async () => {
      const user = userEvent.setup();
      initiateSetPrimary.mockResolvedValue({ data: { state: "st-1" } });
      confirmSetPrimary.mockRejectedValue(new Error("boom"));
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "trigger-set-primary" }),
      );
      await screen.findByTestId("stepup-dialog");

      await user.click(
        screen.getByRole("button", { name: `confirm:${PRIMARY_TITLE}` }),
      );

      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith(
          "Could not set your primary contact email.",
        ),
      );
      expect(refresh).not.toHaveBeenCalled();
      expect(screen.getByTestId("stepup-dialog")).toBeInTheDocument();
    });

    it("re-initiates when the dialog resends", async () => {
      const user = userEvent.setup();
      initiateSetPrimary.mockResolvedValue({ data: { state: "st-1" } });
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "trigger-set-primary" }),
      );
      await screen.findByTestId("stepup-dialog");
      expect(initiateSetPrimary).toHaveBeenCalledTimes(1);

      await user.click(
        screen.getByRole("button", { name: `resend:${PRIMARY_TITLE}` }),
      );
      await waitFor(() => expect(initiateSetPrimary).toHaveBeenCalledTimes(2));
    });

    it("closes the dialog via onOpenChange(false)", async () => {
      const user = userEvent.setup();
      initiateSetPrimary.mockResolvedValue({ data: { state: "st-1" } });
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "trigger-set-primary" }),
      );
      await screen.findByTestId("stepup-dialog");

      await user.click(
        screen.getByRole("button", { name: `close:${PRIMARY_TITLE}` }),
      );

      await waitFor(() =>
        expect(screen.queryByTestId("stepup-dialog")).not.toBeInTheDocument(),
      );
    });
  });

  describe("Unlink sign-in method", () => {
    it("initiates the unlink and opens the dialog with a labelled target", async () => {
      const user = userEvent.setup();
      initiateUnlink.mockResolvedValue({ data: { state: "st-2" } });
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "trigger-unlink" }));

      await waitFor(() => expect(initiateUnlink).toHaveBeenCalledWith(7));
      expect(screen.getByTestId("stepup-title")).toHaveTextContent(
        UNLINK_TITLE,
      );
      // identityLabel maps google-oauth2 → Google account and appends the claim.
      expect(screen.getByTestId("stepup-desc")).toHaveTextContent(
        "Google account (ext@gmail.com)",
      );
    });

    it("tells the two-doors truth: unlinking only removes the sign-in shortcut", async () => {
      const user = userEvent.setup();
      initiateUnlink.mockResolvedValue({ data: { state: "st-2" } });
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "trigger-unlink" }));

      await screen.findByTestId("stepup-dialog");
      expect(screen.getByTestId("stepup-desc")).toHaveTextContent(
        "This removes only that sign-in. Its email address stays on your " +
          "account and can still be used to sign in with Email OTP. To fully " +
          "disconnect this address, also remove its Email OTP.",
      );
    });

    it("toasts and stays closed when initiate fails", async () => {
      const user = userEvent.setup();
      initiateUnlink.mockRejectedValue(new Error("boom"));
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "trigger-unlink" }));

      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith(
          "Could not start removing this sign-in method.",
        ),
      );
      expect(screen.queryByTestId("stepup-dialog")).not.toBeInTheDocument();
    });

    it("confirms the unlink, closes, toasts success and refreshes", async () => {
      const user = userEvent.setup();
      initiateUnlink.mockResolvedValue({ data: { state: "st-2" } });
      confirmUnlink.mockResolvedValue({ data: { ok: true } });
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "trigger-unlink" }));
      await screen.findByTestId("stepup-dialog");

      await user.click(
        screen.getByRole("button", { name: `confirm:${UNLINK_TITLE}` }),
      );

      await waitFor(() =>
        expect(confirmUnlink).toHaveBeenCalledWith(7, "st-2", "123456"),
      );
      expect(toast.success).toHaveBeenCalledWith("Sign-in method removed.");
      expect(refresh).toHaveBeenCalledTimes(1);
      await waitFor(() =>
        expect(screen.queryByTestId("stepup-dialog")).not.toBeInTheDocument(),
      );
    });

    it("re-initiates when the unlink dialog resends", async () => {
      const user = userEvent.setup();
      initiateUnlink.mockResolvedValue({ data: { state: "st-2" } });
      render(<SignInSecurity />);

      await user.click(screen.getByRole("button", { name: "trigger-unlink" }));
      await screen.findByTestId("stepup-dialog");
      expect(initiateUnlink).toHaveBeenCalledTimes(1);

      await user.click(
        screen.getByRole("button", { name: `resend:${UNLINK_TITLE}` }),
      );
      await waitFor(() => expect(initiateUnlink).toHaveBeenCalledTimes(2));
    });
  });
});
