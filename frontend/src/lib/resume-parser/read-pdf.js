import * as pdfjsLib from "pdfjs-dist";

/**
 * @typedef {Object} TextItem
 * @property {string} text
 * @property {number} x        left edge, PDF user-space units
 * @property {number} y        baseline; origin (0,0) is BOTTOM-LEFT in PDF space
 * @property {number} width
 * @property {number} height   ~ font size
 * @property {string} fontName ORIGINAL font name, e.g. "ABCDEE+Arial-BoldMT"
 * @property {boolean} hasEOL  pdf.js end-of-line marker
 */
/** @typedef {TextItem[]} Line */
/** @typedef {Record<string, Line[]>} Sections */

/** Soft-hyphen quirk: some PDFs emit "-" + U+00AD + U+2010; collapse to "-". */
const HYPHEN_QUIRK_RE = /-­‐/g;

/**
 * Configure the pdf.js worker once. The `?url` import is resolved by Vite at
 * build time AND by Vitest (also Vite-based) in tests, so the same code path
 * works in both. In jsdom (no real Worker) pdf.js falls back to a main-thread
 * "fake worker", which is fine for parsing.
 */
async function ensureWorker() {
  if (pdfjsLib.GlobalWorkerOptions.workerSrc) return;
  const mod = await import("pdfjs-dist/build/pdf.worker.min.mjs?url");
  pdfjsLib.GlobalWorkerOptions.workerSrc = mod.default;
}

/**
 * Read a PDF into TextItems, concatenated across pages in reading order.
 * Never throws — returns [] on any failure (partial > nothing).
 *
 * @param {File|Blob|ArrayBuffer|Uint8Array} file
 * @returns {Promise<TextItem[]>}
 */
export async function readPdf(file) {
  let pdf;
  try {
    await ensureWorker();
    const data =
      file instanceof ArrayBuffer || file instanceof Uint8Array
        ? file
        : await file.arrayBuffer();
    pdf = await pdfjsLib.getDocument({ data }).promise;
    const all = [];
    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
      const page = await pdf.getPage(pageNum);
      await page.getOperatorList(); // forces fonts onto commonObjs
      const content = await page.getTextContent();
      for (const raw of content.items) {
        if (!("str" in raw)) continue; // skip marked-content / non-text items
        const item = toTextItem(raw, page.commonObjs);
        if (item) all.push(item);
      }
    }
    return all;
  } catch {
    return [];
  } finally {
    if (pdf) await pdf.destroy(); // release page/font buffers
  }
}

/**
 * Convert one raw pdf.js text item to a TextItem, or null if it should be
 * dropped (pure whitespace that is not an EOL marker).
 * @returns {TextItem|null}
 */
function toTextItem(raw, commonObjs) {
  const hasEOL = Boolean(raw.hasEOL);
  const text = String(raw.str).replace(HYPHEN_QUIRK_RE, "-");
  if (text.trim().length === 0 && !hasEOL) return null;
  return {
    text,
    x: raw.transform[4],
    y: raw.transform[5],
    width: raw.width,
    height: raw.height,
    fontName: recoverFontName(raw.fontName, commonObjs),
    hasEOL,
  };
}

/**
 * Recover the original font name. Non-system fonts come back as loader aliases
 * like "g_d8_f1"; the real name (containing Bold/Italic) is on commonObjs.
 * Falls back to the raw alias if the lookup is empty.
 * @returns {string}
 */
function recoverFontName(alias, commonObjs) {
  try {
    if (commonObjs?.has(alias)) {
      const font = commonObjs.get(alias);
      if (font?.name) return font.name;
    }
  } catch {
    /* commonObjs.get throws if not yet resolved — fall through */
  }
  return alias ?? "";
}

/**
 * Normalize font-name variants to a stable grouping key:
 * strip the "ABCDEE+" subset prefix and lowercase. ("Arial,Bold" and
 * "ABCDEE+Arial-BoldMT" should not be tallied as different fonts.)
 * @param {string} fontName
 * @returns {string}
 */
export function normalizeFontKey(fontName) {
  return String(fontName ?? "")
    .replace(/^[A-Z]{6}\+/, "")
    .toLowerCase();
}
