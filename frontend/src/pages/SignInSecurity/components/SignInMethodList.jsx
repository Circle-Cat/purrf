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
 * (e.g. a verified address whose email sign-in method was removed). Shows
 * the primary state; a non-primary address offers "Remove" — the server
 * refuses to remove the address backing the caller's own current
 * passwordless session, and that rejection surfaces here as a toast — and,
 * if not already primary, "Set as primary contact" (the same step-up flow
 * the sign-in method rows use).
 *
 * @param {Object} props
 * @param {object} props.emailRow
 * @param {{kind: string, id: (number|string)}|null} props.busy - in-flight action.
 * @param {(emailRow: object) => void} [props.onRemove]
 * @param {(emailRow: object) => void} [props.onSetPrimary]
 */
const ContactEmailRow = ({ emailRow, busy, onRemove, onSetPrimary }) => (
  <li className="flex items-center justify-between gap-2 py-3">
    <div className="flex items-center gap-2">
      <span className="font-medium">{emailRow.email}</span>
      {emailRow.isPrimary && <Badge variant="secondary">Primary contact</Badge>}
    </div>
    <div className="flex items-center gap-1">
      {emailRow.otpConfirmed && !emailRow.isPrimary && !!onSetPrimary && (
        <Button
          size="sm"
          variant="ghost"
          disabled={busy !== null}
          onClick={() => onSetPrimary(emailRow)}
        >
          {busy?.kind === "primary" && busy.id === emailRow.emailId
            ? "Setting…"
            : "Set as primary contact"}
        </Button>
      )}
      {!emailRow.isPrimary && !!onRemove && (
        <Button
          size="sm"
          variant="ghost"
          disabled={busy !== null}
          onClick={() => onRemove(emailRow)}
        >
          {busy?.kind === "removeEmail" && busy.id === emailRow.emailId
            ? "Removing…"
            : "Remove"}
        </Button>
      )}
    </div>
  </li>
);

/**
 * Merged list of the caller's sign-in methods and contact emails: the
 * internal (work) identities, if any, then external identities, then the
 * contact-only addresses (emails with no identity claiming them — e.g. a
 * verified address whose email sign-in method was removed). An employee may
 * hold more than one internal identity (e.g. an SSO login plus an OTP-linked
 * corp email). Internal identities cannot be unlinked here; an external
 * identity can always be removed, current session excepted — the always-live
 * email OTP path to the primary contact means removing the last remaining
 * sign-in method can never lock the caller out (the backend additionally
 * refuses the current session's identity and an active employee's corp
 * sign-in).
 *
 * An email sign-in method's row carries its contact-email state: a
 * non-primary address can be set as the primary contact from there. A
 * contact-only address offers the same "Set as primary contact" action when
 * it is not already primary, and "Remove" when it is not the primary
 * contact. A single in-flight action disables every action button on the
 * list.
 *
 * @component
 * @param {Object} props
 * @param {Array<object>} [props.emails] - contact-email rows from `GET /auth/emails`.
 * @param {Array<object>} props.internalIdentities
 * @param {Array<object>} props.externalIdentities
 * @param {boolean} props.isLoading
 * @param {(identity: object) => Promise<void>} props.onUnlink
 * @param {(emailRow: object) => Promise<void>} [props.onSetPrimary] - start promoting a contact email.
 * @param {(emailRow: object) => Promise<void>} [props.onRemove] - remove a non-primary contact-only address.
 */
const SignInMethodList = ({
  emails = [],
  internalIdentities,
  externalIdentities,
  isLoading,
  onUnlink,
  onSetPrimary,
  onRemove,
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

  const handleRemove = async (emailRow) => {
    setBusy({ kind: "removeEmail", id: emailRow.emailId });
    try {
      await onRemove(emailRow);
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
          canUnlink
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
          onRemove={onRemove ? handleRemove : undefined}
          onSetPrimary={onSetPrimary ? handleSetPrimary : undefined}
        />
      ))}
    </ul>
  );
};

export default SignInMethodList;
