/**
 * The public front door for Pub/Sub push.
 *
 * Pub/Sub cannot carry a Cloudflare Access service token -- PushConfig only
 * supports the `x-goog-version` attribute -- so the backend cannot be reached
 * directly without punching a hole in Access. This Worker is that missing
 * credential holder: it verifies Google's OIDC token itself and only then
 * forwards, carrying the service token Pub/Sub could not.
 *
 * It is a door, not a handler. It never parses the notification payload.
 */

const JWKS_CACHE_TTL_SECONDS = 3600;
const GOOGLE_ISSUERS = new Set([
  "https://accounts.google.com",
  "accounts.google.com",
]);

/** Decodes one base64url segment of a JWT into text. */
function decodeSegment(segment) {
  const padded = segment.replace(/-/g, "+").replace(/_/g, "/");
  return atob(
    padded.padEnd(padded.length + ((4 - (padded.length % 4)) % 4), "="),
  );
}

/**
 * Fetches the signing keys, reusing the Cache API so a burst of pushes does
 * not become a burst of requests to Google.
 *
 * @param {string} jwksUrl Where the issuer publishes its public keys.
 * @returns {Promise<object[]>} The JWKS `keys` array.
 */
async function loadKeys(jwksUrl) {
  const cache = caches.default;
  const cacheKey = new Request(jwksUrl);
  let response = await cache.match(cacheKey);

  if (!response) {
    response = await fetch(jwksUrl);
    const cacheable = new Response(response.clone().body, response);
    cacheable.headers.set("cache-control", `max-age=${JWKS_CACHE_TTL_SECONDS}`);
    await cache.put(cacheKey, cacheable.clone());
    response = cacheable;
  }

  const { keys } = await response.json();
  return keys ?? [];
}

/**
 * Verifies a Google-signed OIDC token against the expected audience and the
 * allowed service accounts.
 *
 * Asserting `sub` and not only `aud` is deliberate: the audience is an app
 * label, not a secret, so any Google service account anywhere can mint a
 * token for it.
 *
 * @param {string} token The raw JWT.
 * @param {object} env Worker environment bindings.
 * @returns {Promise<boolean>} True when the caller is one of ours.
 */
async function isTrusted(token, env) {
  const parts = token.split(".");
  if (parts.length !== 3) return false;

  let header;
  let claims;
  try {
    header = JSON.parse(decodeSegment(parts[0]));
    claims = JSON.parse(decodeSegment(parts[1]));
  } catch {
    return false;
  }

  if (!GOOGLE_ISSUERS.has(claims.iss)) return false;
  if (claims.aud !== env.EXPECTED_AUDIENCE) return false;

  // ALLOWED_SUBS is a Terraform-injected secret (never baked into
  // wrangler.jsonc) and so is absent until that secret is set. Missing or
  // empty must fail closed exactly like any other verification failure --
  // an empty allow-list trusts nobody -- rather than let the `.split` below
  // throw an uncaught TypeError and surface an opaque 500 to Pub/Sub instead
  // of a clean 403.
  const allowedSubs = (env.ALLOWED_SUBS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (allowedSubs.length === 0) {
    console.error(
      "pubsub-gateway: ALLOWED_SUBS is missing or empty -- rejecting every caller until it is configured",
    );
    return false;
  }
  if (!allowedSubs.includes(claims.sub)) return false;
  if (
    typeof claims.exp !== "number" ||
    claims.exp <= Math.floor(Date.now() / 1000)
  ) {
    return false;
  }

  const jwk = (await loadKeys(env.JWKS_URL)).find(
    (key) => key.kid === header.kid,
  );
  if (!jwk) return false;

  const publicKey = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const signature = Uint8Array.from(
    atob(parts[2].replace(/-/g, "+").replace(/_/g, "/")),
    (character) => character.charCodeAt(0),
  );
  return crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    publicKey,
    signature,
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
}

export default {
  /**
   * Verifies the caller, then forwards the body to the backend.
   *
   * The origin's status code is returned unchanged: Pub/Sub decides whether
   * to ack or redeliver from it alone, so swallowing an error here would
   * silently drop the message.
   *
   * @param {Request} request Incoming push request.
   * @param {object} env Worker environment bindings.
   * @returns {Promise<Response>} 403, or whatever the origin answered.
   */
  async fetch(request, env) {
    const authorization = request.headers.get("authorization") ?? "";
    const token = authorization.startsWith("Bearer ")
      ? authorization.slice("Bearer ".length)
      : "";

    if (!token || !(await isTrusted(token, env))) {
      return new Response(null, { status: 403 });
    }

    const origin = await fetch(env.ORIGIN_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "CF-Access-Client-Id": env.CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": env.CF_ACCESS_CLIENT_SECRET,
        // Passed on, not consumed: the origin asserts the caller too, so a
        // request arriving some other way carries nothing it will accept.
        authorization,
      },
      body: await request.text(),
    });

    return new Response(origin.body, { status: origin.status });
  },
};
