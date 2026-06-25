// Compiled once at module scope (Global Constraint: no per-item regex).
const NAME_RE = /^[\p{L}\s.'\-]+$/u;
// First alternative: international "+<country> <digits…>" (the leading + keeps
// false positives low). Second: the common US (xxx) xxx-xxxx form.
const PHONE_RE =
  /\+\d{1,3}[\s-]?\d[\d\s-]{5,}\d|\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}/;
const CITY_STATE_RE = /[A-Z][A-Za-z\s]+,\s(?:[A-Z]{2}|[A-Z][a-z]+)/;
const URL_RE = /\S+\.[a-z]+\/\S+/;
const URL_HTTP_RE = /https?:\/\/\S+\.\S+/;
const URL_WWW_RE = /www\.\S+\.\S+/;
const GPA_RE = /[0-4]\.\d{1,2}/;
const EMAIL_RE = /\S+@\S+\.\S+/;
const PAREN_AREA_RE = /\(\d+\)/; // "(123)"
// Tested against a dot-stripped copy of the text so "B.S." / "B.Sc" / "Ph.D"
// reduce to "BS" / "BSc" / "PhD" and match cleanly on word boundaries.
const DEGREE_ABBR_RE =
  /\b(?:bsc?|msc?|ba|ma|beng|meng|btech|mtech|mba|phd|llb|llm|jd)\b/i;

const SCHOOL_KEYWORDS = [
  "college",
  "university",
  "institute",
  "school",
  "academy",
  "polytechnic",
];
const DEGREE_KEYWORDS = [
  "associate",
  "bachelor",
  "master",
  "doctor",
  "phd",
  "ph.d",
];

/** @param {TextItem} i */ export const hasAt = (i) => i.text.includes("@");
/** @param {TextItem} i */ export const hasNumber = (i) => /\d/.test(i.text);
/** @param {TextItem} i */ export const hasComma = (i) => i.text.includes(",");
/** @param {TextItem} i */ export const hasSlash = (i) => i.text.includes("/");
/** @param {TextItem} i */ export const hasParenthesis = (i) =>
  PAREN_AREA_RE.test(i.text);
/** @param {TextItem} i */ export const hasLetter = (i) =>
  /[A-Za-z]/.test(i.text);
/** @param {TextItem} i */ export const isBold = (i) =>
  String(i.fontName).toLowerCase().includes("bold");
/** @param {TextItem} i */ export const isAllUpperWithLetter = (i) =>
  /[A-Z]/.test(i.text) && i.text === i.text.toUpperCase();
/** @param {TextItem} i */ export const has4OrMoreWords = (i) =>
  i.text.trim().split(/\s+/).filter(Boolean).length >= 4;
/** @param {TextItem} i */ export const hasSchool = (i) =>
  SCHOOL_KEYWORDS.some((k) => i.text.toLowerCase().includes(k));
/** @param {TextItem} i */ export const hasDegree = (i) =>
  DEGREE_KEYWORDS.some((k) => i.text.toLowerCase().includes(k)) ||
  DEGREE_ABBR_RE.test(i.text.replace(/\./g, ""));

/** @param {TextItem} i @returns {RegExpMatchArray|null} */
export const matchName = (i) => i.text.match(NAME_RE);
/** @param {TextItem} i @returns {RegExpMatchArray|null} */
export const matchPhone = (i) => i.text.match(PHONE_RE);
/** @param {TextItem} i @returns {RegExpMatchArray|null} */
export const matchCityState = (i) => i.text.match(CITY_STATE_RE);
/** @param {TextItem} i @returns {RegExpMatchArray|null} */
export const matchUrl = (i) => i.text.match(URL_RE);
/** @param {TextItem} i @returns {RegExpMatchArray|null} */
export const matchUrlHttp = (i) => i.text.match(URL_HTTP_RE);
/** @param {TextItem} i @returns {RegExpMatchArray|null} */
export const matchUrlWww = (i) => i.text.match(URL_WWW_RE);
/** @param {TextItem} i @returns {RegExpMatchArray|null} */
export const matchGpa = (i) => i.text.match(GPA_RE);

/**
 * True when a line's text looks like contact info (email/phone/url/City, ST).
 * Used to isolate the profile header and to reject section titles.
 * @param {string} text
 * @returns {boolean}
 */
export const isContactLine = (text) =>
  EMAIL_RE.test(text) ||
  PHONE_RE.test(text) ||
  URL_RE.test(text) ||
  URL_HTTP_RE.test(text) ||
  URL_WWW_RE.test(text) ||
  CITY_STATE_RE.test(text);
