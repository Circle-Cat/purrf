/**
 * Whether the element a step highlights is on the page.
 *
 * @param {string} anchor - The step's `data-tour` value.
 * @returns {boolean}
 */
export const anchorExists = (anchor) =>
  document.querySelector(`[data-tour="${anchor}"]`) !== null;

/**
 * The indices of the steps that would show right now: those whose anchor is
 * on the page. Steps sharing an `alternative` name are variants of one step
 * (the component renders exactly one of their anchors, chosen by its state);
 * should two of them be present anyway, only the first counts.
 *
 * @param {Array<{anchor: string, alternative?: string}>} steps
 * @returns {number[]} Indices into `steps`, in order.
 */
export const visibleIndices = (steps) => {
  const taken = new Set();
  const visible = [];
  steps.forEach((step, index) => {
    if (step.alternative && taken.has(step.alternative)) return;
    if (!anchorExists(step.anchor)) return;
    if (step.alternative) taken.add(step.alternative);
    visible.push(index);
  });
  return visible;
};

/**
 * Waits until at least `minimum` of `steps` are visible, watching the DOM as
 * the page loads.
 *
 * @param {Array<Object>} steps - The steps to look for.
 * @param {number} minimum - How many must be visible.
 * @param {number} timeoutMs - How long to wait before giving up.
 * @returns {Promise<number[] | null>} The visible indices once enough are
 *   present, or null on timeout.
 */
export const waitForAnchors = (steps, minimum, timeoutMs) =>
  new Promise((resolve) => {
    const check = () => {
      const visible = visibleIndices(steps);
      return visible.length >= minimum ? visible : null;
    };
    const found = check();
    if (found || steps.length < minimum) {
      resolve(found);
      return;
    }
    let timer = null;
    const observer = new MutationObserver(() => {
      const visible = check();
      if (visible) finish(visible);
    });
    const finish = (result) => {
      observer.disconnect();
      clearTimeout(timer);
      resolve(result);
    };
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-tour"],
    });
    timer = setTimeout(() => finish(null), timeoutMs);
  });
