import { getTextWithHighestScore } from "./feature-scoring";
import {
  has4OrMoreWords,
  hasAt,
  hasComma,
  hasLetter,
  hasNumber,
  hasParenthesis,
  hasSlash,
  isAllUpperWithLetter,
  isBold,
  matchCityState,
  matchName,
  matchPhone,
  matchUrl,
  matchUrlHttp,
  matchUrlWww,
} from "./lib/features";

// Feature tables (§6.2). · in the spec = returnMatchOnly (third tuple element).
const NAME_FEATURES = [
  [matchName, 3, true],
  [isBold, 2],
  [isAllUpperWithLetter, 2],
  [hasAt, -4],
  [hasNumber, -4],
  [hasParenthesis, -4],
  [hasComma, -4],
  [hasSlash, -4],
  [has4OrMoreWords, -2],
];
const PHONE_FEATURES = [
  [matchPhone, 4, true],
  [hasLetter, -4],
];
const LOCATION_FEATURES = [
  [matchCityState, 4, true],
  [isBold, -1],
  [hasAt, -4],
  [hasParenthesis, -3],
  [hasSlash, -4],
];
const URL_FEATURES = [
  [matchUrl, 4, true],
  [matchUrlHttp, 3, true],
  [matchUrlWww, 3, true],
  [isBold, -1],
  [hasAt, -4],
  [hasParenthesis, -3],
  [hasComma, -4],
  [has4OrMoreWords, -4],
];
const SUMMARY_FEATURES = [
  [has4OrMoreWords, 4],
  [isBold, -1],
  [hasAt, -4],
  [hasParenthesis, -3],
  [matchCityState, -4],
];

/**
 * Extract profile fields from the header lines. email is intentionally NOT
 * extracted (it has no profile target); hasAt survives only as a negative
 * feature on name.
 * @param {Line[]} profileLines
 */
export function extractProfile(profileLines) {
  const items = profileLines.flat();
  return {
    name: getTextWithHighestScore(items, NAME_FEATURES),
    phone: getTextWithHighestScore(items, PHONE_FEATURES),
    location: getTextWithHighestScore(items, LOCATION_FEATURES),
    url: getTextWithHighestScore(items, URL_FEATURES),
    summary: getTextWithHighestScore(items, SUMMARY_FEATURES, {
      concatTies: true,
    }),
  };
}
