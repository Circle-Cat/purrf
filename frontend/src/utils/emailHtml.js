import DOMPurify from "dompurify";

/** A URL the browser would fetch from another host: http(s) or `//host`. */
const REMOTE_URL = /^\s*(https?:)?\/\//i;

/** One `url(...)` in an inline style that points at another host. */
const REMOTE_CSS_URL = /url\(\s*['"]?\s*(https?:)?\/\/[^)]*\)/gi;

/** Attributes that load something as soon as the element is shown. */
const LOADING_ATTRIBUTES = [
  "src",
  "background",
  "poster",
  "href",
  "xlink:href",
];

/** Elements whose `href` is loaded rather than followed. */
const LOADING_HREF_ELEMENTS = new Set(["image", "use", "feimage"]);

/** Whether a srcset names any remote candidate. */
const hasRemoteCandidate = (srcset) =>
  srcset.split(",").some((candidate) => REMOTE_URL.test(candidate));

/** A `cid:` reference to a part of the same message (RFC 2392). */
const CID_URL = /^\s*cid:/i;

/**
 * Points an `<img src="cid:...">` at the stored part it names, and says
 * whether it did.
 *
 * @param {Element} node
 * @param {(contentId: string) => string | null | undefined} inlineImageUrl
 * @returns {boolean}
 */
const resolveInlineImage = (node, inlineImageUrl) => {
  const src = node.getAttribute?.("src");
  if (src == null || !CID_URL.test(src)) return false;
  const raw = src.replace(CID_URL, "").trim();
  let contentId = raw;
  try {
    contentId = decodeURIComponent(raw);
  } catch {
    // Not percent-encoded after all; match it as written.
  }
  const url = inlineImageUrl(contentId);
  if (!url) return false;
  node.setAttribute("src", url);
  return true;
};

/**
 * Strips what one element would load from another host, and says whether it
 * found anything. `keepSrc` spares a `src` already pointed at our own copy of
 * an inline part.
 *
 * @param {Element} node
 * @param {{keepSrc?: boolean}} [options]
 * @returns {boolean}
 */
const stripRemoteContent = (node, { keepSrc = false } = {}) => {
  let stripped = false;
  for (const name of LOADING_ATTRIBUTES) {
    if (keepSrc && name === "src") continue;
    const value = node.getAttribute?.(name);
    if (value == null || !REMOTE_URL.test(value)) continue;
    const isLink =
      (name === "href" || name === "xlink:href") &&
      !LOADING_HREF_ELEMENTS.has(node.nodeName.toLowerCase());
    if (isLink) continue;
    node.removeAttribute(name);
    stripped = true;
  }
  const srcset = node.getAttribute?.("srcset");
  if (srcset != null && hasRemoteCandidate(srcset)) {
    node.removeAttribute("srcset");
    stripped = true;
  }
  const style = node.getAttribute?.("style");
  const localStyle = style?.replace(REMOTE_CSS_URL, "none");
  if (style != null && localStyle !== style) {
    node.setAttribute("style", localStyle);
    stripped = true;
  }
  return stripped;
};

/**
 * Sanitize the HTML of a stored email for display inside a page. `<style>` is
 * dropped as well: its rules would apply to the whole page, not only to the
 * message.
 *
 * Remote images and backgrounds are left out unless the reader asked for
 * them, as mail clients do: fetching them as soon as a message is shown tells
 * the sender it was opened, when, and from which address.
 *
 * An image pasted into the message is a part of it, referenced as
 * `cid:<Content-ID>`; `inlineImageUrl` maps that id to where the part is
 * served. Those load without asking: they come from our own server, not the
 * sender's, so loading them tells the sender nothing.
 *
 * @param {string} html
 * @param {{loadRemoteContent?: boolean,
 *          inlineImageUrl?: (contentId: string) => string | null | undefined}}
 *   [options]
 * @returns {{html: string, remoteContentBlocked: boolean}}
 */
export const sanitizeEmailBody = (
  html,
  { loadRemoteContent = false, inlineImageUrl } = {},
) => {
  let remoteContentBlocked = false;
  const hooked = !loadRemoteContent || inlineImageUrl != null;
  if (hooked) {
    DOMPurify.addHook("afterSanitizeAttributes", (node) => {
      const keepSrc =
        inlineImageUrl != null && resolveInlineImage(node, inlineImageUrl);
      if (!loadRemoteContent && stripRemoteContent(node, { keepSrc })) {
        remoteContentBlocked = true;
      }
    });
  }
  try {
    const clean = DOMPurify.sanitize(html, { FORBID_TAGS: ["style"] });
    return { html: clean, remoteContentBlocked };
  } finally {
    if (hooked) DOMPurify.removeHook("afterSanitizeAttributes");
  }
};

/**
 * Markup a composed email body may carry. Deliberately narrow: the composer
 * authors rich text, and what leaves here has to survive Gmail's own
 * sanitizing anyway, so anything structural (tables, images, styles) or
 * active (script, iframe, event handlers) is dropped rather than sent.
 * Display does not use this list; it uses sanitizeEmailBody above.
 */
export const EMAIL_ALLOWED_TAGS = [
  "p",
  "br",
  "b",
  "strong",
  "i",
  "em",
  "u",
  "ul",
  "ol",
  "li",
  "a",
];

/** Attributes kept on the allowed tags: enough for a working hyperlink. */
export const EMAIL_ALLOWED_ATTR = ["href", "target", "rel"];

/**
 * Sanitize composer HTML down to the tags an outgoing body may carry.
 *
 * @param {string} html
 * @returns {string}
 */
export const sanitizeEmailHtml = (html) =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: EMAIL_ALLOWED_TAGS,
    ALLOWED_ATTR: EMAIL_ALLOWED_ATTR,
  });

/**
 * Classes for the box an email body is rendered in. Paint containment makes
 * the box the containing block for fixed-position content and clips it, so a
 * message cannot lay itself over the rest of the page.
 */
export const EMAIL_BODY_BOX_CLASS = "relative overflow-hidden [contain:paint]";
