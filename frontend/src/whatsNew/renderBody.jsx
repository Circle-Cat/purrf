/**
 * Renders an entry body, turning each `**text**` span into bold text. Nothing
 * else is interpreted, so the rest of the body shows exactly as written.
 *
 * @param {string} body - The entry's body.
 * @returns {Array<string|JSX.Element>} Plain strings and `<strong>` elements.
 */
export const renderBody = (body) =>
  body.split(/\*\*(.+?)\*\*/).map((part, index) =>
    index % 2 === 1 ? (
      <strong key={index} className="font-semibold text-foreground">
        {part}
      </strong>
    ) : (
      part
    ),
  );
