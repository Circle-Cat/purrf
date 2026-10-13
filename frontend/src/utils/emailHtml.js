import DOMPurify from "dompurify";

/**
 * Sanitize the HTML of a stored email for display inside a page. `<style>` is
 * dropped as well: its rules would apply to the whole page, not only to the
 * message.
 *
 * @param {string} html
 * @returns {string}
 */
export const sanitizeEmailBody = (html) =>
  DOMPurify.sanitize(html, { FORBID_TAGS: ["style"] });

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
