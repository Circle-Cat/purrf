/**
 * @typedef {[ (i: TextItem) => boolean, number ]
 *   | [ (i: TextItem) => (RegExpMatchArray|null), number, true ]} FeatureSet
 */

/**
 * Score every item against the feature sets and return the best candidate text.
 *
 * @param {TextItem[]} items
 * @param {FeatureSet[]} featureSets
 * @param {{ concatTies?: boolean }} [opts]
 * @returns {string} best candidate text, or "" when the top score <= 0
 */
export function getTextWithHighestScore(items, featureSets, opts = {}) {
  const { concatTies = false } = opts;
  const scored = items.map((item) => {
    let score = 0;
    let text = item.text;
    for (const [matcher, points, returnMatchOnly] of featureSets) {
      const result = matcher(item);
      if (returnMatchOnly) {
        if (result) {
          score += points;
          text = result[0];
        }
      } else if (result) {
        score += points;
      }
    }
    return { text, score };
  });

  let best = null;
  for (const candidate of scored) {
    if (!best || candidate.score > best.score) best = candidate;
  }
  if (!best || best.score <= 0) return "";
  if (concatTies) {
    return scored
      .filter((c) => c.score === best.score)
      .map((c) => c.text)
      .join(" ");
  }
  return best.text;
}
