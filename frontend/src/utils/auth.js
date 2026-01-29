/**
 * Retrieves the value of the specified cookie by its name.
 *
 * This function searches through the browser's `document.cookie` and returns the value of the cookie
 * that matches the provided `name`. If the cookie is not found, it returns `null`.
 *
 * @param {string} name - The name of the cookie to retrieve.
 * @returns {string|null} The value of the cookie if found, otherwise `null`.
 *
 * @example
 * const jwt = getCookie('CF_Authorization');
 * console.log(jwt);  // Outputs the value of the 'CF_Authorization' cookie or null if not found.
 */
export const getCookie = (name) => {
  const regex = new RegExp(`(?:^|; \\s*)${name}\\s*=\\s*([^;]*)`);
  const match = document.cookie.match(regex);

  return match ? decodeURIComponent(match[1]) : null;
};

/**
 * Generic utility function for parsing a JWT payload
 */
export const getJwtPayload = (jwtString) => {
  if (!jwtString) return null;
  try {
    const parts = jwtString.split(".");
    if (parts.length !== 3) {
      console.warn("JWT format is incorrect, not a valid JWT.");
      return null;
    }
    return JSON.parse(atob(parts[1]));
  } catch (e) {
    console.warn("Failed to decode JWT Payload:", e);
    return null;
  }
};

/**
 * Extracts the username from a Cloudflare Access JWT.
 *
 * This function takes a Cloudflare Access JWT string, decodes it, and extracts the username
 * from the JWT payload. It prioritizes extracting the username from the following fields:
 * 1. `.custom.upn` (Azure)
 * 2. `.custom.email` (Google)
 * 3. `.email` (Other, like one-time PIN)
 *
 * If the username is in an email format, it will return only the username part (before '@').
 *
 * If the decoding or extraction fails, it returns `null`.
 *
 * @param {string} jwtString - The Cloudflare Access JWT string to extract the username from.
 * @returns {string|null} The extracted username, or `null` if extraction fails.
 *
 * @example
 * const jwt = 'your-jwt-token';
 * const username = extractCloudflareUserName(jwt);
 * console.log(username);  // Outputs the extracted username or null if failed.
 */
export const extractCloudflareUserName = (jwtString) => {
  if (!jwtString) {
    return null;
  }
  try {
    const jwtPayload = getJwtPayload(jwtString);
    if (!jwtPayload) return null;
    let extractedName = null;

    // Extract username with priority
    // 1. .custom.upn (Azure)
    if (jwtPayload.custom && jwtPayload.custom.upn) {
      extractedName = jwtPayload.custom.upn;
    }
    // 2. .custom.email (Google)
    else if (jwtPayload.custom && jwtPayload.custom.email) {
      extractedName = jwtPayload.custom.email;
    }
    // 3. .email (Other, such as one-time PIN)
    else if (jwtPayload.email) {
      extractedName = jwtPayload.email;
    }

    // If a username is extracted and it is in email format, remove the domain part
    if (extractedName && extractedName.includes("@")) {
      extractedName = extractedName.split("@")[0];
    }

    return extractedName;
  } catch (error) {
    console.error(
      "Failed to parse or extract username from Cloudflare JWT:",
      error,
    );
    return null;
  }
};

/**
 * Global logout handler that dynamically detects Auth0 vs LDAP users
 */
export const performGlobalLogout = () => {
  // Load base configuration
  const {
    VITE_AUTH0_DOMAIN: auth0Domain,
    VITE_AUTH0_CLIENT_ID: clientId,
    VITE_CF_ACCESS_TENANT_DOMAIN: cfTenantDomain,
  } = import.meta.env;

  const currentOrigin = window.location.origin;
  const appHome = `${currentOrigin}/`;

  // Retrieve current user info to determine identity provider (IdP)
  const jwt = getCookie("CF_Authorization");
  const payload = getJwtPayload(jwt);

  // Determine whether the user is an Auth0 user
  // Signal: the email matches the Auth0 Client ID (case-insensitive)
  const isAuth0User =
    payload && payload.email?.toLowerCase() === clientId.toLowerCase();

  // Environment check: determine whether to skip Cloudflare logout
  const isLocal =
    currentOrigin.includes("localhost") ||
    currentOrigin.includes("127.0.0.1") ||
    currentOrigin.includes("172.31");

  // Build Cloudflare logout chain
  // For all non-local environments, Cloudflare logout is always required
  let cfLogoutStep;
  if (isLocal) {
    cfLogoutStep = appHome;
    console.log(
      "Local environment detected, clearing local state only and skipping external logout.",
    );
  } else {
    // Domain-level logout → tenant-level logout → final redirect to home
    const cfDomainLogout = `${currentOrigin}/cdn-cgi/access/logout?returnTo=${encodeURIComponent(
      appHome,
    )}`;
    cfLogoutStep = `https://${cfTenantDomain}/cdn-cgi/access/logout?returnTo=${encodeURIComponent(
      cfDomainLogout,
    )}`;
  }

  // Final redirect decision
  let finalUrl;

  if (isAuth0User) {
    // Auth0 users must clear the Auth0 session first, then return to the CF logout chain
    console.log("Detected Auth0 user, initiating full logout chain.");
    finalUrl = `https://${auth0Domain}/v2/logout?client_id=${clientId}&returnTo=${encodeURIComponent(
      cfLogoutStep,
    )}`;
  } else {
    // LDAP or other users skip Auth0 and go directly through Cloudflare
    console.log("Detected LDAP or non-Auth0 user, skipping Auth0 logout.");
    finalUrl = cfLogoutStep;
  }

  // Clear local state and perform redirect
  localStorage.clear();
  sessionStorage.clear();

  // Log final redirect URL in development for debugging
  if (import.meta.env.DEV) {
    console.log("Logout redirecting to:", finalUrl);
  }

  window.location.href = finalUrl;
};
