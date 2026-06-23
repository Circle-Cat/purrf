import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Generic step-up OTP confirmation dialog. The parent has already requested an
 * OTP (sent to the current primary) and keeps the signed state; this dialog
 * collects the code and calls `onConfirm(code)`. Shared by switch-primary and
 * unlink-sign-in-method.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {string} props.title
 * @param {string} props.description
 * @param {string} props.confirmLabel
 * @param {string} [props.confirmVariant] - Button variant (e.g. "destructive").
 * @param {(code: string) => Promise<void>} props.onConfirm
 * @param {() => Promise<void>} [props.onResend] - re-send the code (re-runs
 *   initiate and refreshes the bound state in the parent); omit to hide the link.
 */
const StepUpConfirmDialog = ({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  confirmVariant = "default",
  onConfirm,
  onResend,
}) => {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) setCode("");
  }, [open]);

  const handleConfirm = async () => {
    if (!code.trim()) {
      toast.error("Enter the code from your email.");
      return;
    }
    setBusy(true);
    try {
      await onConfirm(code.trim());
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    setBusy(true);
    try {
      await onResend();
      setCode("");
      toast.success("We sent a new code to your primary email.");
    } catch (error) {
      toast.error(
        error?.response?.data?.message ||
          "Could not resend the code. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onOpenChange(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Label htmlFor="stepup-code">Verification code</Label>
          <Input
            id="stepup-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            disabled={busy}
            onChange={(e) => setCode(e.target.value)}
            placeholder="123456"
          />
          <Button
            className="w-full"
            variant={confirmVariant}
            onClick={handleConfirm}
            disabled={busy}
          >
            {busy ? "Verifying…" : confirmLabel}
          </Button>
          {onResend && (
            <Button
              type="button"
              variant="link"
              className="h-auto p-0 text-muted-foreground"
              onClick={handleResend}
              disabled={busy}
            >
              Resend code
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default StepUpConfirmDialog;
