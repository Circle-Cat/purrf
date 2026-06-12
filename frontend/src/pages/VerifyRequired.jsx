import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useAuth } from "@/context/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { performGlobalLogout } from "@/utils/auth";
import { initiateEmailVerification, verifyEmailOtp } from "@/api/emailApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

const STEP_EMAIL = "email";
const STEP_CODE = "code";

const errorMessage = (error) =>
  error?.response?.data?.message || "Something went wrong. Please try again.";

/**
 * Full-screen hard wall: a user with no confirmed contact email must
 * verify one here before reaching any other page. Reachable only via the
 * HardWallGate; offers a logout escape hatch so a user with an unreachable
 * address is never trapped.
 */
const VerifyRequired = () => {
  const { user, refreshAuth } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState(STEP_EMAIL);
  const [email, setEmail] = useState(user?.email || "");
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
      await verifyEmailOtp(stateToken, code.trim());
      await refreshAuth();
      navigate(ROUTE_PATHS.PROFILE, { replace: true });
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

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Verify your email to continue</CardTitle>
          <CardDescription>
            We need a confirmed contact email to deliver application updates and
            round notifications.
          </CardDescription>
        </CardHeader>

        {step === STEP_EMAIL ? (
          <CardContent className="space-y-3">
            <Label htmlFor="verify-email">Email address</Label>
            <Input
              id="verify-email"
              type="email"
              value={email}
              disabled={busy}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
            <Button className="w-full" onClick={sendCode} disabled={busy}>
              {busy ? "Sending…" : "Send code"}
            </Button>
          </CardContent>
        ) : (
          <CardContent className="space-y-3">
            <Label htmlFor="verify-code">Enter the code sent to {email}</Label>
            <Input
              id="verify-code"
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
              <button
                type="button"
                className="text-muted-foreground hover:underline"
                onClick={sendCode}
                disabled={busy}
              >
                Resend code
              </button>
              <button
                type="button"
                className="text-muted-foreground hover:underline"
                onClick={useDifferentEmail}
                disabled={busy}
              >
                Use a different email
              </button>
            </div>
          </CardContent>
        )}

        <CardFooter className="justify-end">
          <Button variant="ghost" onClick={performGlobalLogout}>
            Log out
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
};

export default VerifyRequired;
