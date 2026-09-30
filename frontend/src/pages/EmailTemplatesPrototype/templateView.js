/**
 * Pure helpers the list and preview share: search, placeholder discovery and
 * the preview's HTML (placeholders filled or shown raw, free-text markers
 * highlighted, then sanitized).
 */
import DOMPurify from "dompurify";
import { SAMPLE_VALUES } from "@/pages/EmailTemplatesPrototype/mockData";

const PLACEHOLDER_RE = /\{\{(\w+)\}\}/g;
const MARKER_RE = /\[[A-Z][A-Z0-9 /]*\]/g;

const ALLOWED_TAGS = [
  "p",
  "br",
  "strong",
  "em",
  "ul",
  "ol",
  "li",
  "a",
  "code",
  "mark",
  "span",
];
const ALLOWED_ATTR = ["href", "class", "title"];

const escapeHtml = (text) =>
  text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

/** Distinct `{{name}}` placeholders in a template, in order of appearance. */
export const placeholdersOf = (template) => {
  const text = template.variants.map((v) => v.subject + v.body).join("");
  return [...new Set([...text.matchAll(PLACEHOLDER_RE)].map((m) => m[1]))];
};

/** Distinct `[UPPERCASE]` free-text markers, in order of appearance. */
export const markersOf = (template) => {
  const text = template.variants.map((v) => v.body).join("");
  return [...new Set(text.match(MARKER_RE) ?? [])];
};

/**
 * Subject as plain text: placeholders filled with sample values, or left as
 * written.
 */
export const previewSubject = (subject, showPlaceholders) =>
  showPlaceholders
    ? subject
    : subject.replace(
        PLACEHOLDER_RE,
        (raw, name) => SAMPLE_VALUES[name] ?? raw,
      );

/**
 * Body as sanitized HTML. Filled placeholders are escaped, like the backend
 * does; raw ones are tagged so they stand out; `[UPPERCASE]` markers are
 * highlighted as text the sender still has to write.
 */
export const previewBody = (body, showPlaceholders) => {
  const withPlaceholders = body.replace(PLACEHOLDER_RE, (raw, name) =>
    showPlaceholders
      ? `<code class="placeholder">${raw}</code>`
      : escapeHtml(SAMPLE_VALUES[name] ?? raw),
  );
  const withMarkers = withPlaceholders.replace(
    MARKER_RE,
    (marker) =>
      `<mark class="marker" title="Filled in by the sender">${marker}</mark>`,
  );
  return DOMPurify.sanitize(withMarkers, { ALLOWED_TAGS, ALLOWED_ATTR });
};

/** Case-insensitive substring match on name, key and any variant's subject. */
export const matchesSearch = (template, term) => {
  const needle = term.trim().toLowerCase();
  if (!needle) return true;
  return (
    template.name.toLowerCase().includes(needle) ||
    template.key.toLowerCase().includes(needle) ||
    template.variants.some((v) => v.subject.toLowerCase().includes(needle))
  );
};
