/**
 * Builds the LaunchDarkly context for an authenticated user.
 *
 * @param {{ sub: string, userId: number, email: string, identityType: string }} user
 * @returns {import("launchdarkly-react-client-sdk").LDContext}
 */
export function toLDContext(user) {
  return {
    kind: "user",
    key: user.sub,
    userId: user.userId,
    email: user.email,
    identity_type: user.identityType,
  };
}
