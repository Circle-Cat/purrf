import { isBold } from "./features";

const GAP_FACTOR = 1.4;
const BULLET_ONLY_RE = /^[•‣◦▪*\-–]+$/;

/** Most common value in a list (or null). @param {number[]} values */
function mostCommon(values) {
  if (values.length === 0) return null;
  const counts = new Map();
  let best = null;
  let bestN = 0;
  for (const v of values) {
    const n = (counts.get(v) ?? 0) + 1;
    counts.set(v, n);
    if (n > bestN) {
      bestN = n;
      best = v;
    }
  }
  return best;
}

/** First item on a line that is not a pure bullet glyph. @param {Line} line */
function firstNonBullet(line) {
  return line.find((t) => !BULLET_ONLY_RE.test(t.text.trim())) ?? line[0];
}

function lineY(line) {
  return line[0]?.y ?? null;
}

/** Fallback split: new subsection when a line's first item turns bold. */
function splitOnBold(lines) {
  const subs = [];
  let current = [];
  let prevBold = false;
  for (const line of lines) {
    const item = firstNonBullet(line);
    const bold = item ? isBold(item) : false;
    if (current.length && bold && !prevBold) {
      subs.push(current);
      current = [];
    }
    current.push(line);
    prevBold = bold;
  }
  if (current.length) subs.push(current);
  return subs.length ? subs : [lines];
}

/**
 * Split a multi-entry section into subsections.
 * @param {Line[]} lines
 * @returns {Line[][]}
 */
export function splitIntoSubsections(lines) {
  if (lines.length === 0) return [];

  const gaps = [];
  for (let i = 1; i < lines.length; i++) {
    const prev = lineY(lines[i - 1]);
    const y = lineY(lines[i]);
    if (prev != null && y != null) gaps.push(Math.round(prev - y));
  }
  const typical = mostCommon(gaps);

  let subs = [lines];
  if (typical != null) {
    subs = [];
    let current = [lines[0]];
    for (let i = 1; i < lines.length; i++) {
      const prev = lineY(lines[i - 1]) ?? 0;
      const y = lineY(lines[i]) ?? 0;
      if (Math.round(prev - y) > typical * GAP_FACTOR) {
        subs.push(current);
        current = [lines[i]];
      } else {
        current.push(lines[i]);
      }
    }
    subs.push(current);
  }

  if (subs.length <= 1) subs = splitOnBold(lines);
  return subs;
}
