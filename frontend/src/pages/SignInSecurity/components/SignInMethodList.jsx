import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { providerLabel, isEmailMethod } from "@/pages/SignInSecurity/providers";

/**
 * One sign-in method row. Only an email sign-in method exposes contact-email
 * management: when its email maps to a synced contact email, the row shows its
 * primary state and — if that email is verified and not already primary — a
 * "Set as primary contact" action (the same step-up flow the standalone email
 * card used). The caller passes `emailRow` only for email methods, so non-email
 * methods (SSO, email-and-password) never show either. An external,
 * non-current-session method can also be removed.
 *
 * @param {Object} props
 * @param {object} props.identity
 * @param {boolean} props.internal
 * @param {boolean} props.canUnlink
 * @param {object|undefined} props.emailRow - matching contact-email row, if any.
 * @param {{kind: string, id: (number|string)}|null} props.busy - in-flight action.
 * @param {(identity: object) => void} [props.onUnlink]
 * @param {(emailRow: object) => void} [props.onSetPrimary]
 */
const IdentityRow = ({
  identity,
  internal,
  canUnlink,
  emailRow,
  busy,
  onUnlink,
  onSetPrimary,
}) => {
  const isBusy = busy !== null;
  const canSetPrimary =
    !!onSetPrimary && emailRow && emailRow.otpConfirmed && !emailRow.isPrimary;

  return (
    <li className="flex items-center justify-between gap-2 py-3">
      <div className="flex items-center gap-2">
        <span className="font-medium">
          {providerLabel(identity.subjectIdentifier)}
        </span>
        {identity.emailClaim && (
          <span className="text-sm text-muted-foreground">
            {identity.emailClaim}
          </span>
        )}
        {internal && <Badge>Internal</Badge>}
        {identity.isCurrentSession && (
          <Badge variant="outline">Current session</Badge>
        )}
        {emailRow?.isPrimary && (
          <Badge variant="secondary">Primary contact</Badge>
        )}
      </div>
      <div className="flex items-center gap-1">
        {canSetPrimary && (
          <Button
            size="sm"
            variant="ghost"
            disabled={isBusy}
            onClick={() => onSetPrimary(emailRow)}
          >
            {busy?.kind === "primary" && busy.id === emailRow.emailId
              ? "Setting…"
              : "Set as primary contact"}
          </Button>
        )}
        {canUnlink && !identity.isCurrentSession && (
          <Button
            size="sm"
            variant="ghost"
            disabled={isBusy}
            onClick={() => onUnlink(identity)}
          >
            {busy?.kind === "unlink" && busy.id === identity.identityId
              ? "Removing…"
              : "Remove"}
          </Button>
        )}
      </div>
    </li>
  );
};

/**
 * One contact-only email row: an address with no sign-in identity behind it
 * (an unverified backup, or a verified address whose email method was
 * removed). Shows the primary/unverified state; an unverified address offers
 * a "Verify" action, which is what unlocks it as a sign-in method.
 *
 * @param {Object} props
 * @param {object} props.emailRow
 * @param {{kind: string, id: (number|string)}|null} props.busy - in-flight action.
 * @param {(emailRow: object) => void} [props.onVerify]
 */
const ContactEmailRow = ({ emailRow, busy, onVerify }) => (
  <li className="flex items-center justify-between gap-2 py-3">
    <div className="flex items-center gap-2">
      <span className="font-medium">{emailRow.email}</span>
      {emailRow.isPrimary && <Badge variant="secondary">Primary contact</Badge>}
      {!emailRow.otpConfirmed && <Badge variant="outline">Unverified</Badge>}
    </div>
    {!emailRow.otpConfirmed && !!onVerify && (
      <Button
        size="sm"
        variant="ghost"
        disabled={busy !== null}
        onClick={() => onVerify(emailRow)}
      >
        Verify
      </Button>
    )}
  </li>
);

/**
 * Merged list of the caller's sign-in methods and contact emails: the
 * internal (work) identities, if any, then external identities, then the
 * contact-only addresses (emails with no identity claiming them — e.g. an
 * unverified backup added without OTP). An employee may hold more than one
 * internal identity (e.g. an SSO login plus an OTP-linked corp email).
 * Internal identities cannot be unlinked here; an external identity can be
 * unless it is the only remaining sign-in method (the backend additionally
 * refuses the current session's identity and an active employee's corp
 * sign-in).
 *
 * An email sign-in method's row carries its contact-email state: a verified,
 * non-primary address can be set as the primary contact from there. A
 * contact-only unverified address offers "Verify" instead, which unlocks it
 * as a sign-in method. A single in-flight action disables every action
 * button on the list.
 *
 * @component
 * @param {Object} props
 * @param {Array<object>} [props.emails] - contact-email rows from `GET /auth/emails`.
 * @param {Array<object>} props.internalIdentities
 * @param {Array<object>} props.externalIdentities
 * @param {boolean} props.isLoading
 * @param {(identity: object) => Promise<void>} props.onUnlink
 * @param {(emailRow: object) => Promise<void>} [props.onSetPrimary] - start promoting a contact email.
 * @param {(emailRow: object) => void} [props.onVerify] - start verifying a contact-only address.
 */
const SignInMethodList = ({
  emails = [],
  internalIdentities,
  externalIdentities,
  isLoading,
  onUnlink,
  onSetPrimary,
  onVerify,
}) => {
  const [busy, setBusy] = useState(null);

  // Keyed case-insensitively so a contact row matches its identity's email
  // claim regardless of casing, mirroring the backend's lower-cased join.
  const emailByAddress = new Map(
    emails.map((email) => [(email.email || "").toLowerCase(), email]),
  );

  // The synced contact-email row for an identity, but only for email sign-in
  // methods — non-email methods do not expose contact-email management.
  const emailRowFor = (identity) =>
    isEmailMethod(identity.subjectIdentifier)
      ? emailByAddress.get((identity.emailClaim || "").toLowerCase())
      : undefined;

  // Addresses no email sign-in method claims render as their own rows.
  const claimedAddresses = new Set(
    [...internalIdentities, ...externalIdentities]
      .filter((identity) => isEmailMethod(identity.subjectIdentifier))
      .map((identity) => (identity.emailClaim || "").toLowerCase()),
  );
  const contactOnlyEmails = emails.filter(
    (email) => !claimedAddresses.has((email.email || "").toLowerCase()),
  );

  const handleUnlink = async (identity) => {
    setBusy({ kind: "unlink", id: identity.identityId });
    try {
      await onUnlink(identity);
    } finally {
      setBusy(null);
    }
  };

  const handleSetPrimary = async (emailRow) => {
    setBusy({ kind: "primary", id: emailRow.emailId });
    try {
      await onSetPrimary(emailRow);
    } finally {
      setBusy(null);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (
    !internalIdentities.length &&
    !externalIdentities.length &&
    !contactOnlyEmails.length
  ) {
    return (
      <p className="text-sm text-muted-foreground">No sign-in methods yet.</p>
    );
  }

  const total = internalIdentities.length + externalIdentities.length;
  const canUnlink = total > 1;

  return (
    <ul className="divide-y">
      {internalIdentities.map((identity) => (
        <IdentityRow
          key={identity.identityId}
          identity={identity}
          internal
          canUnlink={false}
          emailRow={emailRowFor(identity)}
          busy={busy}
          onSetPrimary={handleSetPrimary}
        />
      ))}
      {externalIdentities.map((identity) => (
        <IdentityRow
          key={identity.identityId}
          identity={identity}
          canUnlink={canUnlink}
          emailRow={emailRowFor(identity)}
          busy={busy}
          onUnlink={handleUnlink}
          onSetPrimary={handleSetPrimary}
        />
      ))}
      {contactOnlyEmails.map((emailRow) => (
        <ContactEmailRow
          key={`email-${emailRow.emailId}`}
          emailRow={emailRow}
          busy={busy}
          onVerify={onVerify}
        />
      ))}
    </ul>
  );
};

export default SignInMethodList;
