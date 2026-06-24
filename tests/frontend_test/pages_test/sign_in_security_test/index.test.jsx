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
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

// Child list mock exposes buttons that drive the page's action callbacks.
// Both the set-primary and unlink actions are now triggered from this list.
vi.mock("@/pages/SignInSecurity/components/SignInMethodList", () => ({
  default: ({
    emails,
    internalIdentities,
    externalIdentities,
    isLoading,
    onUnlink,
    onSetPrimary,
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
    </div>
  ),
}));

vi.mock("@/pages/SignInSecurity/components/AddSignInMethodDialog", () => ({
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

const PRIMARY_TITLE = "Switch primary email";
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

  it("renders only the sign-in methods card and no email-address card", () => {
    render(<SignInSecurity />);

    expect(screen.queryByText("Email addresses")).not.toBeInTheDocument();
    expect(screen.getByText("Sign-in methods")).toBeInTheDocument();
    expect(
      screen.getByText(/The accounts you can use to sign in to Purrf\./),
    ).toBeInTheDocument();
  });

  it("renders the sign-in method list and no email-address list", () => {
    render(<SignInSecurity />);

    expect(screen.queryByTestId("email-address-list")).not.toBeInTheDocument();
    expect(screen.getByTestId("sign-in-method-list")).toBeInTheDocument();
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

  describe("Add sign-in method", () => {
    it("opens the add dialog and refreshes after a verified add", async () => {
      const user = userEvent.setup();
      render(<SignInSecurity />);

      await user.click(
        screen.getByRole("button", { name: "Add sign-in method" }),
      );
      expect(screen.getByTestId("add-dialog")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "add-onAdded" }));
      expect(refresh).toHaveBeenCalledTimes(1);
    });
  });

  describe("Switch primary email", () => {
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
      expect(toast.success).toHaveBeenCalledWith("Primary email updated.");
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
          "Could not switch your primary email.",
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
      // identityLabel maps google-oauth2 → Google and appends the email claim.
      expect(screen.getByTestId("stepup-desc")).toHaveTextContent(
        "Google (ext@gmail.com)",
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
