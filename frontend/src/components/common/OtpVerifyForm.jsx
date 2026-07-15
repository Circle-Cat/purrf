import { useState } from "react";
import { toast } from "sonner";

import { initiateEmailVerification, verifyEmailOtp } from "@/api/emailApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const STEP_EMAIL = "email";
const STEP_CODE = "code";

const errorMessage = (error) =>
  error?.response?.data?.message || "Something went wrong. Please try again.";

/**
 * Two-step email OTP form: enter an address → send a code → enter the code →
 * verify. Shared by the hard wall (VerifyRequired) and the Settings "add
 * email" flow.
 *
 * Renders only the form body; the surrounding chrome (card / dialog, title,
 * escape hatch) and what happens after a successful verify are supplied by the
 * parent via `onVerified`.
 *
 * @component
 * @param {Object} props
 * @param {string} [props.initialEmail] - prefilled address (e.g. the login email).
 * @param {(result: object) => (void|Promise<void>)} props.onVerified - called with
 *   the verify API result after success; the parent decides what happens next.
 * @param {string} [props.idPrefix] - DOM id prefix for the inputs (default "otp").
 * @param {boolean} [props.lockEmail] - render the address read-only (the
 *   needs-link wall only ever verifies the sign-in's own email).
 */
const OtpVerifyForm = ({
  initialEmail = "",
  onVerified,
  idPrefix = "otp",
  lockEmail = false,
}) => {
  const [step, setStep] = useState(STEP_EMAIL);
  const [email, setEmail] = useState(initialEmail);
  const [stateToken, setStateToken] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const sendCode = async () => {
    const target = email.trim();
    if (!target) {
      toast.error("Enter an email address first.");
      return;
    }
    setBusy(true);
    try {
      const { data } = await initiateEmailVerification(target);
      setStateToken(data.state);
      setStep(STEP_CODE);
      toast.success(`We sent a 6-digit code to ${target}.`);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    if (!code.trim()) {
      toast.error("Enter the code from your email.");
      return;
    }
    setBusy(true);
    try {
      const { data } = await verifyEmailOtp(stateToken, code.trim());
      await onVerified?.(data);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const useDifferentEmail = () => {
    setStep(STEP_EMAIL);
    setCode("");
    setStateToken(null);
  };

  if (step === STEP_EMAIL) {
    return (
      <div className="space-y-3">
        <Label htmlFor={`${idPrefix}-email`}>Email address</Label>
        <Input
          id={`${idPrefix}-email`}
          type="email"
          value={email}
          disabled={busy || lockEmail}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
        <Button className="w-full" onClick={sendCode} disabled={busy}>
          {busy ? "Sending…" : "Send code"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Label htmlFor={`${idPrefix}-code`}>Enter the code sent to {email}</Label>
      <Input
        id={`${idPrefix}-code`}
        inputMode="numeric"
        autoComplete="one-time-code"
        value={code}
        disabled={busy}
        onChange={(e) => setCode(e.target.value)}
        placeholder="123456"
      />
      <Button className="w-full" onClick={verify} disabled={busy}>
        {busy ? "Verifying…" : "Verify"}
      </Button>
      <div className="flex justify-between text-sm">
        <Button
          type="button"
          variant="link"
          className="h-auto p-0 text-muted-foreground"
          onClick={sendCode}
          disabled={busy}
        >
          Resend code
        </Button>
        {!lockEmail && (
          <Button
            type="button"
            variant="link"
            className="h-auto p-0 text-muted-foreground"
            onClick={useDifferentEmail}
            disabled={busy}
          >
            Use a different email
          </Button>
        )}
      </div>
    </div>
  );
};

export default OtpVerifyForm;
