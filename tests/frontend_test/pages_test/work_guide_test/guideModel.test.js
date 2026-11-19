import { describe, expect, it } from "vitest";
import {
  CHAPTER_PERMISSIONS,
  GUIDE_PERMISSIONS,
  blockHeading,
  findFlow,
  headingsOf,
  neighbours,
  searchFlows,
  visibleChapters,
} from "@/pages/WorkGuide/guideModel";
import { INBOX_PERMISSIONS, PERMISSIONS } from "@/constants/Permissions";

const chapters = [
  {
    id: "start-here",
    title: "Start here",
    description: "Start",
    permissions: GUIDE_PERMISSIONS,
    flows: [
      {
        id: "how-email-works",
        title: "How email works in Purrf",
        blocks: [{ type: "text", text: "One shared mailbox." }],
      },
    ],
  },
  {
    id: "inbox",
    title: "Inbox",
    description: "Inbox",
    permissions: INBOX_PERMISSIONS,
    flows: [
      {
        id: "inbox-reply",
        title: "Reply to an email",
        blocks: [
          {
            type: "steps",
            steps: [{ text: "Write and click **Send reply**." }],
          },
          { type: "goodToKnow", items: ["Drafts are kept."] },
        ],
      },
    ],
  },
  {
    id: "recruiting",
    title: "Recruiting",
    description: "Recruiting",
    permissions: CHAPTER_PERMISSIONS.recruiting,
    flows: [
      {
        id: "recruiting-advance",
        title: "Advance or reject an application",
        permissions: [PERMISSIONS.RECRUITING_APPLICATION_ADVANCE],
        blocks: [{ type: "text", text: "Use the board." }],
      },
      {
        id: "recruiting-review-posting",
        title: "Review a job posting",
        permissions: [PERMISSIONS.RECRUITING_JOB_APPROVE],
        blocks: [
          {
            type: "table",
            columns: ["Where", "What"],
            rows: [["Postings", "Approve the draft"]],
          },
        ],
      },
    ],
  },
  {
    id: "mentorship",
    title: "Mentorship",
    description: "Mentorship",
    permissions: CHAPTER_PERMISSIONS.mentorship,
    flows: [
      {
        id: "mentorship-find",
        title: "Find a participant",
        permissions: [
          PERMISSIONS.MENTORSHIP_ADMIN_READ,
          PERMISSIONS.MENTORSHIP_ADMIN_WRITE,
        ],
        blocks: [{ type: "heading", text: "Search" }],
      },
    ],
  },
];

const ids = (flows) => flows.map((flow) => flow.id);

describe("GUIDE_PERMISSIONS", () => {
  it("is the union of every chapter's permissions without repeats", () => {
    const union = [
      ...CHAPTER_PERMISSIONS.inbox,
      ...CHAPTER_PERMISSIONS.recruiting,
      ...CHAPTER_PERMISSIONS.mentorship,
    ];
    expect([...GUIDE_PERMISSIONS].sort()).toEqual([...new Set(union)].sort());
    expect(GUIDE_PERMISSIONS).toContain(
      PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
    );
    expect(GUIDE_PERMISSIONS).not.toContain(PERMISSIONS.LEAVE_ADMIN);
  });
});

describe("visibleChapters", () => {
  it("hides chapters the viewer has no permission for", () => {
    const visible = visibleChapters(chapters, [
      PERMISSIONS.MENTORSHIP_ADMIN_READ,
    ]);
    expect(visible.map((c) => c.id)).toEqual(["start-here", "mentorship"]);
  });

  it("returns nothing without a matching permission", () => {
    expect(visibleChapters(chapters, [PERMISSIONS.LEAVE_ADMIN])).toEqual([]);
    expect(visibleChapters(chapters, [])).toEqual([]);
  });

  it("lets a flow's own permissions override its chapter's", () => {
    const visible = visibleChapters(chapters, [
      PERMISSIONS.RECRUITING_JOB_APPROVE,
    ]);
    const recruiting = visible.find((c) => c.id === "recruiting");
    expect(ids(recruiting.flows)).toEqual(["recruiting-review-posting"]);
  });
});

describe("findFlow", () => {
  it("finds a flow with its chapter", () => {
    const found = findFlow(chapters, "inbox-reply");
    expect(found.chapter.id).toBe("inbox");
    expect(found.flow.title).toBe("Reply to an email");
  });

  it("returns null for a hidden or unknown flow", () => {
    const visible = visibleChapters(chapters, [
      PERMISSIONS.MENTORSHIP_ADMIN_READ,
    ]);
    expect(findFlow(visible, "recruiting-advance")).toBeNull();
    expect(findFlow(visible, "nope")).toBeNull();
  });
});

describe("neighbours", () => {
  it("has no previous flow for the first one", () => {
    const { previous, next } = neighbours(chapters, "how-email-works");
    expect(previous).toBeNull();
    expect(next.id).toBe("inbox-reply");
  });

  it("crosses into the next chapter's first flow", () => {
    expect(neighbours(chapters, "inbox-reply").next.id).toBe(
      "recruiting-advance",
    );
    expect(neighbours(chapters, "recruiting-advance").previous.id).toBe(
      "inbox-reply",
    );
  });

  it("has no next flow for the last one", () => {
    expect(neighbours(chapters, "mentorship-find").next).toBeNull();
  });

  it("returns two nulls for an unknown flow", () => {
    expect(neighbours(chapters, "nope")).toEqual({
      previous: null,
      next: null,
    });
  });
});

describe("searchFlows", () => {
  it("treats regex characters as plain text", () => {
    expect(() => searchFlows(chapters, "reply (")).not.toThrow();
    expect(searchFlows(chapters, "reply (")).toEqual([]);
  });

  it("returns nothing for a word that is nowhere", () => {
    expect(searchFlows(chapters, "zzz")).toEqual([]);
  });

  it("matches step text across bold labels, ignoring case", () => {
    expect(ids(searchFlows(chapters, "SEND REPLY"))).toEqual(["inbox-reply"]);
  });

  it("matches titles, tables, headings and Good to know items", () => {
    expect(ids(searchFlows(chapters, "job posting"))).toEqual([
      "recruiting-review-posting",
    ]);
    expect(ids(searchFlows(chapters, "approve the draft"))).toEqual([
      "recruiting-review-posting",
    ]);
    expect(ids(searchFlows(chapters, "search"))).toEqual(["mentorship-find"]);
    expect(ids(searchFlows(chapters, "drafts are kept"))).toEqual([
      "inbox-reply",
    ]);
  });

  it("returns nothing for a blank query", () => {
    expect(searchFlows(chapters, "   ")).toEqual([]);
  });
});

describe("blockHeading", () => {
  it("names the blocks that carry a section heading", () => {
    expect(blockHeading({ type: "steps", steps: [] })).toBe("Steps");
    expect(
      blockHeading({ type: "steps", title: "Rules of thumb", steps: [] }),
    ).toBe("Rules of thumb");
    expect(blockHeading({ type: "goodToKnow", items: [] })).toBe(
      "Good to know",
    );
    expect(blockHeading({ type: "heading", text: "Search" })).toBe("Search");
    expect(blockHeading({ type: "text", text: "Hi" })).toBeNull();
    expect(blockHeading({ type: "diagram", name: "emailFlow" })).toBeNull();
  });
});

describe("headingsOf", () => {
  it("lists the sections in order with unique ids", () => {
    const flow = {
      id: "f",
      title: "F",
      blocks: [
        { type: "text", text: "Intro" },
        { type: "steps", steps: [] },
        { type: "heading", text: "Rules of thumb" },
        { type: "heading", text: "Steps" },
        { type: "goodToKnow", items: [] },
      ],
    };
    expect(headingsOf(flow)).toEqual([
      { id: "steps", text: "Steps" },
      { id: "rules-of-thumb", text: "Rules of thumb" },
      { id: "steps-2", text: "Steps" },
      { id: "good-to-know", text: "Good to know" },
    ]);
  });
});
