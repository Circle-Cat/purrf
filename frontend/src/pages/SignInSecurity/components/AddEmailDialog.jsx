import { useState } from "react";
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

import { addContactEmail } from "@/api/emailApi";

/**
 * Dialog for adding a backup contact email — no OTP round-trip. The address
 * is recorded unverified and stays contact-only; the user must verify it
 * afterwards to use it as a sign-in method. On success it closes and asks the
 * parent to refresh the settings view.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {() => (void|Promise<void>)} props.onAdded - called after a successful add.
 */
const AddEmailDialog = ({ open, onOpenChange, onAdded }) => {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const target = email.trim();
    if (!target) {
      toast.error("Enter an email address first.");
      return;
    }
    setSubmitting(true);
    try {
      await addContactEmail(target);
      toast.success("Email added. Verify it to use it for signing in.");
      setEmail("");
      onOpenChange(false);
      await onAdded?.();
    } catch (error) {
      toast.error(
        error?.response?.data?.message || "Could not add this email.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add an email</DialogTitle>
          <DialogDescription>
            The address is added as a contact email right away; verify it before
            you can use it to sign in.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor="add-email-address">Email address</Label>
          <Input
            id="add-email-address"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            disabled={submitting}
          />
        </div>
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Adding…" : "Add email"}
        </Button>
      </DialogContent>
    </Dialog>
  );
};

export default AddEmailDialog;
