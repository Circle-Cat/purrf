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
 * Classes for the box an email body is rendered in. Paint containment makes
 * the box the containing block for fixed-position content and clips it, so a
 * message cannot lay itself over the rest of the page.
 */
export const EMAIL_BODY_BOX_CLASS = "relative overflow-hidden [contain:paint]";
