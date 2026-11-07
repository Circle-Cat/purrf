import { visibleNavItems } from "@/components/layout/navItems";

/**
 * Fills in the steps whose body depends on the viewer. A step with `navGroup`
 * gets, as its body, the `tourText` of each item in that sidebar group the
 * viewer can see, in sidebar order. Such a step is dropped when the viewer
 * sees none of them. Other steps pass through unchanged.
 *
 * @param {Array<Object>} steps - A guide's steps as defined.
 * @param {{permissions: string[], flags: Record<string, any>}} viewer - The
 *   viewer's permissions and feature flag values.
 * @returns {Array<Object>} The steps to run, each with a string or
 *   string-array `body`.
 */
export const resolveSteps = (steps, viewer) =>
  steps.flatMap((step) => {
    if (!step.navGroup) return [step];
    const body = visibleNavItems(step.navGroup, viewer)
      .map((item) => item.tourText)
      .filter(Boolean);
    return body.length > 0 ? [{ ...step, body }] : [];
  });
