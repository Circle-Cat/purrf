const POLL_MS = 100;

/**
 * Waits for `[data-whats-new="<anchor>"]` to render, then scrolls it into
 * view and outlines it for a while. An outline takes no layout space, so
 * nothing on the page moves. Gives up quietly if the element never appears.
 *
 * @param {string} anchor - The element's `data-whats-new` value.
 * @param {Object} [options]
 * @param {number} [options.timeoutMs=5000] - How long to wait for the element.
 * @param {number} [options.outlineMs=3000] - How long the outline stays.
 * @returns {() => void} Cancels the wait and removes the outline early.
 */
export const highlightAnchor = (
  anchor,
  { timeoutMs = 5000, outlineMs = 3000 } = {},
) => {
  const selector = `[data-whats-new="${anchor}"]`;
  let pollTimer = null;
  let outlineTimer = null;
  let restore = null;
  const startedAt = Date.now();

  const outline = (element) => {
    element.scrollIntoView?.({ behavior: "smooth", block: "center" });
    const { outline: prevOutline, outlineOffset: prevOffset } = element.style;
    element.style.outline = "3px solid var(--primary)";
    element.style.outlineOffset = "3px";
    restore = () => {
      element.style.outline = prevOutline;
      element.style.outlineOffset = prevOffset;
      restore = null;
    };
    outlineTimer = setTimeout(() => restore?.(), outlineMs);
  };

  const poll = () => {
    const element = document.querySelector(selector);
    if (element) {
      outline(element);
      return;
    }
    if (Date.now() - startedAt >= timeoutMs) return;
    pollTimer = setTimeout(poll, POLL_MS);
  };
  poll();

  return () => {
    clearTimeout(pollTimer);
    clearTimeout(outlineTimer);
    restore?.();
  };
};
