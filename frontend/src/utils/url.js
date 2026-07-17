/**
 * Validate and normalize a user-supplied URL so it is safe to place in an
 * `<a href>`. Only `http:`/`https:` URLs are allowed; anything else (notably
 * `javascript:` and `data:` URLs, which execute in the current origin when
 * clicked) is rejected. A bare host like "linkedin.com/in/me" is upgraded to
 * "https://linkedin.com/in/me".
 *
 * @param {string} raw - The untrusted URL string (e.g. a profile LinkedIn link).
 * @returns {string|null} A safe http(s) URL, or null if the input cannot be
 *   trusted and should not be rendered as a link.
 */
export function safeHttpUrl(raw) {
  if (typeof raw !== "string") return null;

  const trimmed = raw.trim();
  if (!trimmed) return null;

  // A URL has an explicit scheme if it starts with e.g. "https:" or
  // "javascript:". Schemes other than http(s) are rejected; a string with no
  // scheme is treated as a bare host and upgraded to https.
  const hasScheme = /^[a-z][a-z0-9+.-]*:/i.test(trimmed);
  const candidate = hasScheme ? trimmed : `https://${trimmed}`;

  try {
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (!url.hostname) return null;
    return candidate;
  } catch {
    return null;
  }
}
