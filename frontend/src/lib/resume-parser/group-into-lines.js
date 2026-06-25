import { normalizeFontKey } from "./read-pdf";

const MIN_CHAR_WIDTH = 3;
const MAX_CHAR_WIDTH = 20;
const BULLET_GLYPHS = "•‣◦▪";
const NEEDS_SPACE_LEFT = new RegExp(`[:,|.${BULLET_GLYPHS}]$`);
const NEEDS_SPACE_RIGHT = new RegExp(`^[|${BULLET_GLYPHS}]`);

/** @param {number[]} arr */
function median(arr) {
  if (arr.length === 0) return null;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * Estimate a typical character width (PDF units). Pick the most common
 * normalized (fontName,height) pair and average width/length over it; fall
 * back to the global median when that pair has < 3 samples or the value is
 * out of the sane [3,20] range.
 *
 * @param {TextItem[]} items
 * @returns {number|null} null when no usable items
 */
export function typicalCharWidth(items) {
  const nonBlank = items.filter((i) => i.text.trim().length > 0);
  if (nonBlank.length === 0) return null;
  const widths = nonBlank.map((i) => i.width / i.text.length);
  const globalMedian = median(widths);

  const keyOf = (i) =>
    `${normalizeFontKey(i.fontName)}|${Math.round(i.height)}`;
  const counts = new Map();
  for (const i of nonBlank)
    counts.set(keyOf(i), (counts.get(keyOf(i)) ?? 0) + 1);
  let bestKey = null;
  let bestN = 0;
  for (const [k, n] of counts) {
    if (n > bestN) {
      bestN = n;
      bestKey = k;
    }
  }

  let value;
  if (bestN < 3) {
    value = globalMedian;
  } else {
    const matched = nonBlank
      .filter((i) => keyOf(i) === bestKey)
      .map((i) => i.width / i.text.length);
    value = matched.reduce((a, b) => a + b, 0) / matched.length;
  }
  if (value < MIN_CHAR_WIDTH || value > MAX_CHAR_WIDTH) value = globalMedian;
  // The median fallback can itself be out of range (e.g. every item is
  // pathologically wide), so hard-clamp the final value into the sane range.
  return Math.min(MAX_CHAR_WIDTH, Math.max(MIN_CHAR_WIDTH, value));
}

/**
 * Group items into visual lines and merge fragmented items within each line.
 * @param {TextItem[]} items
 * @returns {Line[]}
 */
export function groupIntoLines(items) {
  const lines = [];
  let current = [];
  for (const item of items) {
    if (item.text.trim().length > 0) current.push(item);
    if (item.hasEOL && current.length) {
      lines.push(current);
      current = [];
    }
  }
  if (current.length) lines.push(current);

  const tcw = typicalCharWidth(items);
  if (tcw == null) return lines;
  return lines.map((line) => mergeLine(line, tcw));
}

/** Merge items whose horizontal gap to the left neighbor is <= tcw. */
function mergeLine(line, tcw) {
  const sorted = [...line].sort((a, b) => a.x - b.x);
  const out = [];
  for (const item of sorted) {
    const left = out[out.length - 1];
    if (left) {
      const gap = item.x - (left.x + left.width);
      if (gap <= tcw) {
        const space =
          NEEDS_SPACE_LEFT.test(left.text) || NEEDS_SPACE_RIGHT.test(item.text)
            ? " "
            : "";
        left.text = left.text + space + item.text;
        left.width = item.x + item.width - left.x;
        continue;
      }
    }
    out.push({ ...item });
  }
  return out;
}
