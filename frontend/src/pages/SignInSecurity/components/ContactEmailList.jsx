import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * List of the caller's contact emails from `GET /auth/emails`. A verified
 * address doubles as a sign-in method; an unverified one is contact-only and
 * shows an "Unverified" badge plus a "Verify" action that starts the email
 * OTP flow for that address.
 *
 * @component
 * @param {Object} props
 * @param {Array<object>} props.emails - contact-email rows.
 * @param {boolean} props.isLoading
 * @param {(emailRow: object) => void} props.onVerify - start verifying an address.
 */
const ContactEmailList = ({ emails, isLoading, onVerify }) => {
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (!emails.length) {
    return <p className="text-sm text-muted-foreground">No emails yet.</p>;
  }

  return (
    <ul className="divide-y">
      {emails.map((emailRow) => (
        <li
          key={emailRow.emailId}
          className="flex items-center justify-between gap-2 py-3"
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">{emailRow.email}</span>
            {emailRow.isPrimary && (
              <Badge variant="secondary">Primary contact</Badge>
            )}
            {!emailRow.otpConfirmed && (
              <Badge variant="outline">Unverified</Badge>
            )}
          </div>
          {!emailRow.otpConfirmed && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onVerify(emailRow)}
            >
              Verify
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
};

export default ContactEmailList;
