import { Badge } from "@/components/ui/badge";

/**
 * Read-only list of the caller's contact email addresses, each tagged with
 * its primary and verification state. Row actions (make primary, verify,
 * remove) are added by later stories.
 *
 * @component
 * @param {Object} props
 * @param {Array<object>} props.emails - email rows from `GET /auth/emails`.
 * @param {boolean} props.isLoading
 */
const EmailAddressList = ({ emails, isLoading }) => {
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
        <li key={email.emailId} className="flex items-center gap-2 py-3">
          <span className="font-medium">{email.email}</span>
          {email.isPrimary && <Badge>Primary</Badge>}
          <Badge variant={email.otpConfirmed ? "secondary" : "outline"}>
            {email.otpConfirmed ? "Verified" : "Pending"}
          </Badge>
        </li>
      ))}
    </ul>
  );
};

export default EmailAddressList;
