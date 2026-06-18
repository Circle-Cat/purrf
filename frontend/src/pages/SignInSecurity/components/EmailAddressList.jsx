import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * List of the caller's contact email addresses, each tagged with its primary
 * and verification state. A verified non-primary address can be promoted to
 * primary (step-up OTP, handled by the parent). Emails are not removed here —
 * they are synced from sign-in methods.
 *
 * @component
 * @param {Object} props
 * @param {Array<object>} props.emails - email rows from `GET /auth/emails`.
 * @param {boolean} props.isLoading
 * @param {(email: object) => Promise<void>} props.onSetPrimary - start promoting a row.
 */
const EmailAddressList = ({ emails, isLoading, onSetPrimary }) => {
  const [busyId, setBusyId] = useState(null);

  const handleSetPrimary = async (email) => {
    setBusyId(email.emailId);
    try {
      await onSetPrimary(email);
    } finally {
      setBusyId(null);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (!emails.length) {
    return (
      <p className="text-sm text-muted-foreground">No email addresses yet.</p>
    );
  }

  return (
    <ul className="divide-y">
      {emails.map((email) => (
        <li
          key={email.emailId}
          className="flex items-center justify-between gap-2 py-3"
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">{email.email}</span>
            {email.isPrimary && <Badge>Primary</Badge>}
            <Badge variant={email.otpConfirmed ? "secondary" : "outline"}>
              {email.otpConfirmed ? "Verified" : "Pending"}
            </Badge>
          </div>
          {!email.isPrimary && email.otpConfirmed && (
            <Button
              size="sm"
              variant="ghost"
              disabled={busyId !== null}
              onClick={() => handleSetPrimary(email)}
            >
              {busyId === email.emailId ? "Setting…" : "Set as primary"}
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
};

export default EmailAddressList;
