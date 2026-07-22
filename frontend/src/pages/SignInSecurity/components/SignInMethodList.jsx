import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { providerLabel } from "@/pages/SignInSecurity/providers";

/**
 * Group the account's confirmed emails and sign-in identities by address.
 *
 * The page is address-centric: one row per address, carrying every capability
 * that address grants (a `Google account` sign-in, `Email OTP` passwordless, or
 * both). An email and the identities whose `emailClaim` matches it collapse into
 * a single group so an address is never listed twice. Identities with no email
 * claim (rare) key on their subject identifier and render as their own,
 * chip-less row.
 *
 * @param {Array<object>} emails - confirmed contact-email rows.
 * @param {Array<object>} internalIdentities - INTERNAL sign-in identities.
 * @param {Array<object>} externalIdentities - EXTERNAL sign-in identities.
 * @returns {Array<{
 *   key: string,
 *   address: string,
 *   hasEmail: boolean,
 *   emailRow: (object|undefined),
 *   identities: Array<object>,
 * }>} Address groups, primary-contact address first.
 */
const buildAddressGroups = (emails, internalIdentities, externalIdentities) => {
  const groups = new Map();
  const order = [];

  const ensure = (key, address) => {
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        address,
        hasEmail: false,
        emailRow: undefined,
        identities: [],
      });
      order.push(key);
    }
    return groups.get(key);
  };

  emails.forEach((email) => {
    const group = ensure((email.email || "").toLowerCase(), email.email);
    group.emailRow = email;
    group.hasEmail = true;
  });

  const addIdentity = (identity, internal) => {
    const claim = identity.emailClaim || "";
    // Claimless identities can't share an address, so they key on their sub and
    // render as a lone provider row; email-claimed ones join their address.
    const key = claim
      ? claim.toLowerCase()
      : `identity:${identity.subjectIdentifier}`;
    const group = ensure(
      key,
      claim || providerLabel(identity.subjectIdentifier),
    );
    if (claim) group.hasEmail = true;
    group.identities.push({
      // Keep the raw identity so callbacks receive the exact object the caller
      // passed in, unenriched.
      raw: identity,
      internal,
      // Active employees keep their corp sign-ins; only external identities
      // can be unlinked here (the backend enforces the same rule).
      canUnlink: !internal,
    });
  };

  internalIdentities.forEach((identity) => addIdentity(identity, true));
  externalIdentities.forEach((identity) => addIdentity(identity, false));

  const ordered = order.map((key) => groups.get(key));
  // Primary-contact address leads; everything else keeps insertion order.
  const primary = ordered.filter((group) => group.emailRow?.isPrimary);
  const rest = ordered.filter((group) => !group.emailRow?.isPrimary);
  return [...primary, ...rest];
};

/**
 * The capability chips for an address, in reading order: each sign-in
 * identity's provider label, then `Email OTP` when the address is a confirmed
 * (passwordless-capable) email. Deduplicated, so an `email|` identity and its
 * confirmed email row surface a single `Email OTP` chip.
 *
 * @param {{hasEmail: boolean, emailRow: (object|undefined), identities: Array<{raw: object}>}} group
 * @returns {string[]} Distinct capability labels; empty for a chip-less row.
 */
const capabilityChips = (group) => {
  if (!group.hasEmail) return [];
  const chips = [];
  const add = (label) => {
    if (!chips.includes(label)) chips.push(label);
  };
  group.identities.forEach((entry) =>
    add(providerLabel(entry.raw.subjectIdentifier)),
  );
  if (group.emailRow?.otpConfirmed) add("Email OTP");
  return chips;
};

/**
 * One address row: the address, its status badges (primary / internal /
 * current session), its capability chips, and the actions that apply to it —
 * set the contact email as primary, remove a sign-in identity, or remove the
 * email. When an address grants more than one sign-in path (an identity plus
 * Email OTP) and both are removable, a note explains that removing just one
 * leaves the other live.
 *
 * @param {Object} props
 * @param {object} props.group - one entry from {@link buildAddressGroups}.
 * @param {boolean} props.accountIsInternal - the account is internal (holds an
 *   INTERNAL identity or a confirmed corp email), so the primary contact is
 *   corp-managed and cannot be changed here.
 * @param {{kind: string, id: (number|string)}|null} props.busy - in-flight action.
 * @param {(identity: object) => void} [props.onUnlink]
 * @param {(emailRow: object) => void} [props.onSetPrimary]
 * @param {(emailRow: object) => void} [props.onRemove]
 */
const AddressRow = ({
  group,
  accountIsInternal,
  busy,
  onUnlink,
  onSetPrimary,
  onRemove,
}) => {
  const isBusy = busy !== null;
  const { emailRow, identities } = group;

  // An address is internal if it carries an INTERNAL sign-in identity OR its
  // email is a corp-domain address. Row-less corp employees keep no identity
  // row, so `isCorp` is their only remaining internal signal.
  const isInternal =
    identities.some((entry) => entry.internal) || !!emailRow?.isCorp;
  const isCurrentSession = identities.some(
    (entry) => entry.raw.isCurrentSession,
  );
  const chips = capabilityChips(group);

  const removableIdentities = identities.filter(
    (entry) => entry.canUnlink && !entry.raw.isCurrentSession,
  );
  const canSetPrimary =
    !accountIsInternal &&
    !!onSetPrimary &&
    !!emailRow &&
    emailRow.otpConfirmed &&
    !emailRow.isPrimary;
  // A corp email on an internal account is a locked contact — the backend
  // refuses to remove it (an active employee must keep a corp address), so
  // the control is withheld here too.
  const canRemoveEmail =
    !!onRemove &&
    !!emailRow &&
    !emailRow.isPrimary &&
    !(accountIsInternal && emailRow.isCorp);
  // Removing one path never fully disconnects an address that has two removable
  // ones — say so, so nobody assumes "Remove ... sign-in" also kills Email OTP.
  const showMultiPathHint =
    !!onUnlink &&
    removableIdentities.length > 0 &&
    canRemoveEmail &&
    emailRow.otpConfirmed;

  return (
    <li className="flex flex-col gap-1 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{group.address}</span>
          {emailRow?.isPrimary && (
            <Badge variant="secondary">Primary contact</Badge>
          )}
          {isInternal && <Badge>Internal</Badge>}
          {isCurrentSession && <Badge variant="outline">Current session</Badge>}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1">
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
          {!!onUnlink &&
            removableIdentities.map((entry) => (
              <Button
                key={entry.raw.identityId}
                size="sm"
                variant="ghost"
                disabled={isBusy}
                onClick={() => onUnlink(entry.raw)}
              >
                {busy?.kind === "unlink" && busy.id === entry.raw.identityId
                  ? "Removing…"
                  : `Remove ${providerLabel(entry.raw.subjectIdentifier)} sign-in`}
              </Button>
            ))}
          {canRemoveEmail && (
            <Button
              size="sm"
              variant="ghost"
              disabled={isBusy}
              onClick={() => onRemove(emailRow)}
            >
              {busy?.kind === "removeEmail" && busy.id === emailRow.emailId
                ? "Removing…"
                : "Remove email"}
            </Button>
          )}
        </div>
      </div>
      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          {chips.map((chip) => (
            <Badge
              key={chip}
              variant="outline"
              className="font-normal text-muted-foreground"
            >
              {chip}
            </Badge>
          ))}
        </div>
      )}
      {showMultiPathHint && (
        <p className="text-xs text-muted-foreground">
          Removing one method won&apos;t fully disconnect this address — remove
          both its sign-in and Email OTP to cut it off.
        </p>
      )}
    </li>
  );
};

/**
 * Address-centric list of how the account signs in: one row per address, each
 * showing the sign-in paths that address grants as capability chips
 * (`Google account`, `Email OTP`) alongside its status badges, plus the actions
 * that apply to it. An address is never listed twice — a confirmed email and
 * the identities claiming it collapse into one row.
 *
 * Actions per row: set a confirmed, non-primary email as the primary contact
 * (hidden for internal accounts, whose primary is corp-managed); remove an
 * external, non-current-session sign-in identity; and remove a non-primary
 * email. A confirmed primary email is always a passwordless login path, so
 * removing the last identity can never lock the caller out. A single in-flight
 * action disables every button.
 *
 * @component
 * @param {Object} props
 * @param {Array<object>} [props.emails] - confirmed contact-email rows from `GET /auth/emails`.
 * @param {Array<object>} props.internalIdentities
 * @param {Array<object>} props.externalIdentities
 * @param {boolean} props.isLoading
 * @param {(identity: object) => Promise<void>} [props.onUnlink] - remove a sign-in identity.
 * @param {(emailRow: object) => Promise<void>} [props.onSetPrimary] - start promoting a contact email.
 * @param {(emailRow: object) => Promise<void>} [props.onRemove] - remove a non-primary email.
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

  const groups = buildAddressGroups(
    emails,
    internalIdentities,
    externalIdentities,
  );
  // Internal for UI purposes when the account holds an INTERNAL identity OR any
  // confirmed corp email — the latter covers row-less corp employees, who have
  // no internal identity row but whose corp primary is still corp-locked.
  const accountIsInternal =
    internalIdentities.length > 0 || emails.some((email) => email.isCorp);

  const runBusy = async (kind, id, action) => {
    setBusy({ kind, id });
    try {
      await action();
    } finally {
      setBusy(null);
    }
  };

  const handleUnlink = (identity) =>
    runBusy("unlink", identity.identityId, () => onUnlink(identity));
  const handleSetPrimary = (emailRow) =>
    runBusy("primary", emailRow.emailId, () => onSetPrimary(emailRow));
  const handleRemove = (emailRow) =>
    runBusy("removeEmail", emailRow.emailId, () => onRemove(emailRow));

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (groups.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No sign-in methods yet.</p>
    );
  }

  return (
    <ul className="divide-y">
      {groups.map((group) => (
        <AddressRow
          key={group.key}
          group={group}
          accountIsInternal={accountIsInternal}
          busy={busy}
          onUnlink={onUnlink ? handleUnlink : undefined}
          onSetPrimary={onSetPrimary ? handleSetPrimary : undefined}
          onRemove={onRemove ? handleRemove : undefined}
        />
      ))}
    </ul>
  );
};

export default SignInMethodList;
