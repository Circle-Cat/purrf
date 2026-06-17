import { Badge } from "@/components/ui/badge";

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

const IdentityRow = ({ identity, internal }) => (
  <li className="flex items-center gap-2 py-3">
    <span className="font-medium">
      {providerLabel(identity.subjectIdentifier)}
    </span>
    {identity.emailClaim && (
      <span className="text-sm text-muted-foreground">
        {identity.emailClaim}
      </span>
    )}
    {internal && <Badge>Internal</Badge>}
  </li>
);

/**
 * Read-only list of the caller's linked sign-in methods: the single internal
 * (work) identity, if any, followed by external identities. Unlink actions are
 * added by a later story.
 *
 * @component
 * @param {Object} props
 * @param {object|null} props.internalIdentity
 * @param {Array<object>} props.externalIdentities
 * @param {boolean} props.isLoading
 */
const SignInMethodList = ({
  internalIdentity,
  externalIdentities,
  isLoading,
}) => {
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (!internalIdentity && !externalIdentities.length) {
    return (
      <p className="text-sm text-muted-foreground">No sign-in methods yet.</p>
    );
  }

  return (
    <ul className="divide-y">
      {internalIdentity && <IdentityRow identity={internalIdentity} internal />}
      {externalIdentities.map((identity) => (
        <IdentityRow key={identity.identityId} identity={identity} />
      ))}
    </ul>
  );
};

export default SignInMethodList;
