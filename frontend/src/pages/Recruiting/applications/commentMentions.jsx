const MENTION_TOKEN_RE = /@\[(\d+)\]/g;

/**
 * Finds an in-progress "@query" ending exactly at cursorPos, if any -- the
 * text between the nearest preceding "@" and the cursor, with no
 * whitespace or existing token delimiters in between. Never matches inside
 * an already-inserted "@[id]" token, since "[" and "]" are excluded from
 * the query character class.
 *
 * @param {string} text
 * @param {number} cursorPos
 * @returns {{start: number, query: string} | null}
 */
export const getActiveMentionQuery = (text, cursorPos) => {
  const upToCursor = text.slice(0, cursorPos);
  const match = upToCursor.match(/@([^\s@[\]]*)$/);
  if (!match) return null;
  return { start: match.index, query: match[1] };
};

/**
 * Replaces the in-progress "@query" span [start, cursorPos) with a mention
 * token for userId, followed by a trailing space, and reports where the
 * cursor should land afterward.
 *
 * @param {string} text
 * @param {number} start
 * @param {number} cursorPos
 * @param {number} userId
 * @returns {{text: string, cursorPos: number}}
 */
export const insertMention = (text, start, cursorPos, userId) => {
  const token = `@[${userId}] `;
  const newText = text.slice(0, start) + token + text.slice(cursorPos);
  return { text: newText, cursorPos: start + token.length };
};

/**
 * Splits a comment body into plain-text and highlighted-mention segments,
 * resolving each "@[id]" token's display name from that comment's own
 * `mentions` list. A token with no matching entry (shouldn't happen given
 * backend validation, but the renderer must not crash on it) is dropped
 * rather than shown as literal markup.
 *
 * @param {string} body
 * @param {{userId: number, name: string}[]} mentions
 * @returns {import("react").ReactNode[]}
 */
export const renderCommentBody = (body, mentions = []) => {
  const nameById = new Map(mentions.map((m) => [m.userId, m.name]));
  const nodes = [];
  let lastIndex = 0;
  let key = 0;

  for (const match of body.matchAll(MENTION_TOKEN_RE)) {
    const [token, idStr] = match;
    const name = nameById.get(Number(idStr));
    if (match.index > lastIndex) {
      nodes.push(body.slice(lastIndex, match.index));
    }
    if (name) {
      nodes.push(
        <span key={`mention-${key++}`} className="font-medium text-primary">
          @{name}
        </span>,
      );
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < body.length) {
    nodes.push(body.slice(lastIndex));
  }
  return nodes;
};
