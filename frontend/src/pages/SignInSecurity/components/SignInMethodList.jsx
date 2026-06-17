import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const PROVIDER_LABELS = {
  "google-oauth2": "Google",
  google: "Google",
  email: "Email",
  auth0: "Email & password",
};

/**
 * Human label for an identity's provider, parsed from the `provider|id`
 * prefix of its subject identifier.
 *
 * @param {string} subjectIdentifier
 * @returns {string}
 */
const providerLabel = (subjectIdentifier) => {
  const provider = (subjectIdentifier || "").split("|")[0];
  return PROVIDER_LABELS[provider] || provider || "Unknown";
};

const IdentityRow = ({ identity, internal, canUnlink, busyId, onUnlink }) => (
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
        <Badge variant="secondary">Primary sign-in</Badge>
      )}
    </div>
    {canUnlink && !identity.isCurrentSession && (
      <Button
        size="sm"
        variant="ghost"
        disabled={busyId !== null}
        onClick={() => onUnlink(identity)}
      >
        {busyId === identity.identityId ? "Removing…" : "Unlink"}
      </Button>
    )}
  </li>
);

/**
 * List of the caller's linked sign-in methods: the single internal (work)
 * identity, if any, followed by external identities. The internal identity
 * cannot be unlinked here; an external identity can be unless it is the only
 * remaining sign-in method (the backend additionally refuses the current
 * session's identity and an active employee's corp sign-in).
 *
 * @component
 * @param {Object} props
 * @param {object|null} props.internalIdentity
 * @param {Array<object>} props.externalIdentities
 * @param {boolean} props.isLoading
 * @param {(identity: object) => Promise<void>} props.onUnlink
 */
const SignInMethodList = ({
  internalIdentity,
  externalIdentities,
  isLoading,
  onUnlink,
}) => {
  const [busyId, setBusyId] = useState(null);

  const handleUnlink = async (identity) => {
    setBusyId(identity.identityId);
    try {
      await onUnlink(identity);
    } finally {
      setBusyId(null);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (!internalIdentity && !externalIdentities.length) {
    return (
      <p className="text-sm text-muted-foreground">No sign-in methods yet.</p>
    );
  }

  const total = (internalIdentity ? 1 : 0) + externalIdentities.length;
  const canUnlink = total > 1;

  return (
    <ul className="divide-y">
      {internalIdentity && (
        <IdentityRow identity={internalIdentity} internal canUnlink={false} />
      )}
      {externalIdentities.map((identity) => (
        <IdentityRow
          key={identity.identityId}
          identity={identity}
          canUnlink={canUnlink}
          busyId={busyId}
          onUnlink={handleUnlink}
        />
      ))}
    </ul>
  );
};

export default SignInMethodList;
