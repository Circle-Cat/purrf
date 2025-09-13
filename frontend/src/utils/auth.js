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
    const parts = jwtString.split(".");
    if (parts.length !== 3) {
      console.warn("JWT format is incorrect, not a valid JWT.");
      return null;
    }

    const payloadBase64 = parts[1];
    const decodedPayloadStr = atob(payloadBase64);

    if (!decodedPayloadStr) {
      console.warn("Failed to decode JWT Payload.");
      return null;
    }

    const jwtPayload = JSON.parse(decodedPayloadStr);

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
