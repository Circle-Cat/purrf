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

/**
 * Strips what one element would load from another host, and says whether it
 * found anything.
 *
 * @param {Element} node
 * @returns {boolean}
 */
const stripRemoteContent = (node) => {
  let stripped = false;
  for (const name of LOADING_ATTRIBUTES) {
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
 * @param {string} html
 * @param {{loadRemoteContent?: boolean}} [options]
 * @returns {{html: string, remoteContentBlocked: boolean}}
 */
export const sanitizeEmailBody = (html, { loadRemoteContent = false } = {}) => {
  let remoteContentBlocked = false;
  if (!loadRemoteContent) {
    DOMPurify.addHook("afterSanitizeAttributes", (node) => {
      if (stripRemoteContent(node)) remoteContentBlocked = true;
    });
  }
  try {
    const clean = DOMPurify.sanitize(html, { FORBID_TAGS: ["style"] });
    return { html: clean, remoteContentBlocked };
  } finally {
    if (!loadRemoteContent) DOMPurify.removeHook("afterSanitizeAttributes");
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
