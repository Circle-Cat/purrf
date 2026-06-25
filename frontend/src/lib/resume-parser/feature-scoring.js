/**
 * @typedef {[ (i: TextItem) => boolean, number ]
 *   | [ (i: TextItem) => (RegExpMatchArray|null), number, true ]} FeatureSet
 */

/**
 * Score every item against the feature sets and return the best candidate text.
 *
 * Items start as candidates scored by every matching feature. When a
 * `returnMatchOnly` feature matches a strict SUBSTRING of an item (e.g. a phone
 * number embedded in a longer contact line), that substring becomes its OWN
 * candidate scored only by that feature — so the surrounding line's negative
 * features (e.g. `hasLetter`) do not drag the extracted value down. When the
 * match spans the whole item, its score folds into that item as usual.
 *
 * @param {TextItem[]} items
 * @param {FeatureSet[]} featureSets
 * @param {{ concatTies?: boolean, allowNonPositive?: boolean }} [opts]
 * @returns {string} best candidate text; "" when the top score <= 0, unless
 *   allowNonPositive is set (then the top candidate is returned regardless)
 */
export function getTextWithHighestScore(items, featureSets, opts = {}) {
  const { concatTies = false, allowNonPositive = false } = opts;
  const candidates = items.map((item) => ({ text: item.text, score: 0 }));

  items.forEach((item, idx) => {
    for (const [matcher, points, returnMatchOnly] of featureSets) {
      const result = matcher(item);
      if (!result) continue;
      if (returnMatchOnly) {
        const matched = result[0];
        if (matched === item.text) {
          candidates[idx].score += points;
        } else {
          // Substring match → isolated candidate, free of the line's features.
          candidates.push({ text: matched, score: points });
        }
      } else {
        candidates[idx].score += points;
      }
    }
  });

  let best = null;
  for (const candidate of candidates) {
    if (!best || candidate.score > best.score) best = candidate;
  }
  if (!best) return "";
  if (!allowNonPositive && best.score <= 0) return "";
  if (concatTies) {
    return candidates
      .filter((c) => c.score === best.score)
      .map((c) => c.text.trim())
      .join(" ");
  }
  return best.text;
}
