import { INBOX_PERMISSIONS, PERMISSIONS } from "@/constants/Permissions";

/**
 * Who each business chapter of the Work guide is for, any-of. Kept here
 * rather than in the content so the sidebar can gate the guide without
 * loading the guide itself.
 *
 * @type {{inbox: string[], recruiting: string[], mentorship: string[]}}
 */
export const CHAPTER_PERMISSIONS = Object.freeze({
  inbox: INBOX_PERMISSIONS,
  recruiting: [
    PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
    PERMISSIONS.RECRUITING_JOB_WRITE,
    PERMISSIONS.RECRUITING_JOB_APPROVE,
  ],
  mentorship: [
    PERMISSIONS.MENTORSHIP_ADMIN_READ,
    PERMISSIONS.MENTORSHIP_ADMIN_WRITE,
    PERMISSIONS.MENTORSHIP_APPROVE,
  ],
});

/**
 * Any of these opens the Work guide: the union of every chapter's
 * permissions.
 *
 * @type {string[]}
 */
export const GUIDE_PERMISSIONS = [
  ...new Set(Object.values(CHAPTER_PERMISSIONS).flat()),
];

const hasAny = (required, permissions) =>
  required.some((p) => permissions.includes(p));

/**
 * The chapters and flows this viewer may see. A flow's own `permissions`
 * replaces its chapter's; a chapter left without flows is dropped.
 *
 * @param {Array<Object>} chapters - Guide chapters.
 * @param {string[]} permissions - The viewer's permissions.
 * @returns {Array<Object>} Copies of the visible chapters with only their
 *   visible flows.
 */
export const visibleChapters = (chapters, permissions) =>
  chapters
    .map((chapter) => ({
      ...chapter,
      flows: chapter.flows.filter((flow) =>
        hasAny(flow.permissions ?? chapter.permissions, permissions),
      ),
    }))
    .filter((chapter) => chapter.flows.length > 0);

/**
 * Finds a flow by id.
 *
 * @param {Array<Object>} chapters - Chapters to look in.
 * @param {string} flowId - The flow's id.
 * @returns {{chapter: Object, flow: Object} | null} The flow and its chapter,
 *   or null when no chapter holds it.
 */
export const findFlow = (chapters, flowId) => {
  for (const chapter of chapters) {
    const flow = chapter.flows.find((f) => f.id === flowId);
    if (flow) return { chapter, flow };
  }
  return null;
};

/**
 * The flows before and after a flow, reading the chapters in order, so the
 * last flow of a chapter leads into the first flow of the next.
 *
 * @param {Array<Object>} chapters - Chapters in reading order.
 * @param {string} flowId - The current flow's id.
 * @returns {{previous: Object|null, next: Object|null}}
 */
export const neighbours = (chapters, flowId) => {
  const flows = chapters.flatMap((chapter) => chapter.flows);
  const index = flows.findIndex((flow) => flow.id === flowId);
  if (index === -1) return { previous: null, next: null };
  return {
    previous: flows[index - 1] ?? null,
    next: flows[index + 1] ?? null,
  };
};

const blockText = (block) => {
  switch (block.type) {
    case "text":
    case "heading":
      return [block.text];
    case "steps":
      return [block.title ?? "", ...block.steps.map((step) => step.text)];
    case "table":
      return [...block.columns, ...block.rows.flat()];
    case "goodToKnow":
      return block.items;
    default:
      return [];
  }
};

const plain = (text) => text.replaceAll("**", "").toLowerCase();

/**
 * Flows whose title, intro or block text contains the query, ignoring case
 * and the `**` label marks. The query is plain text, never a pattern.
 *
 * @param {Array<Object>} chapters - Chapters to search.
 * @param {string} query - What the viewer typed.
 * @returns {Array<Object>} Matching flows in reading order; empty for a blank
 *   query.
 */
export const searchFlows = (chapters, query) => {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  return chapters
    .flatMap((chapter) => chapter.flows)
    .filter((flow) =>
      [flow.title, flow.intro ?? "", ...flow.blocks.flatMap(blockText)].some(
        (text) => plain(text).includes(needle),
      ),
    );
};

/**
 * The section heading a block puts on the page, if any.
 *
 * @param {Object} block - A flow block.
 * @returns {string|null} The heading text, or null for a block without one.
 */
export const blockHeading = (block) => {
  switch (block.type) {
    case "heading":
      return block.text;
    case "steps":
      return block.title ?? "Steps";
    case "goodToKnow":
      return "Good to know";
    default:
      return null;
  }
};

const slug = (text) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

/**
 * The flow's section headings in page order, each with an id unique within
 * the flow, for the "On this page" list and the headings' anchors.
 *
 * @param {Object} flow - A guide flow.
 * @returns {Array<{id: string, text: string}>}
 */
export const headingsOf = (flow) => {
  const seen = new Map();
  return flow.blocks
    .map(blockHeading)
    .filter((text) => text !== null)
    .map((text) => {
      const base = slug(text) || "section";
      const count = (seen.get(base) ?? 0) + 1;
      seen.set(base, count);
      return { id: count === 1 ? base : `${base}-${count}`, text };
    });
};
