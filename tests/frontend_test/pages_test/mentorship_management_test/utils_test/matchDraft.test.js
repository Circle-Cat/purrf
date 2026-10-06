import { describe, it, expect } from "vitest";
import {
  differsFromMatcher,
  mentorChoices,
  mentorOptionLabel,
  problemText,
  savedRow,
  shownRow,
  slotsWithChanges,
} from "@/pages/MentorshipManagement/utils/matchDraft";

const matchedItem = {
  mentee: { userId: 201, name: "Cara Wang" },
  mentor: { userId: 105, name: "Gil Ko" },
  recommendationReason: "Saved reason.",
  matcherMentor: { userId: 101, name: "Ann Lee" },
  matcherReason: "Matcher reason.",
  candidates: [
    { userId: 102, name: "Dan Ma", score: 0.91 },
    { userId: 105, name: "Gil Ko", score: 0.3 },
  ],
};

const unmatchedItem = {
  person: { userId: 203, name: "Hal Wu" },
  role: "mentee",
  recommendationReason: "",
  matcherMentor: null,
  matcherReason: "",
  candidates: [],
};

describe("savedRow and shownRow", () => {
  it("reads a matched item and an unmatched mentee alike, ids as strings", () => {
    expect(savedRow(matchedItem)).toEqual({
      menteeId: "201",
      mentorId: "105",
      recommendationReason: "Saved reason.",
    });
    expect(savedRow(unmatchedItem)).toEqual({
      menteeId: "203",
      mentorId: null,
      recommendationReason: "",
    });
  });

  it("prefers the unsaved change", () => {
    const changes = {
      201: {
        mentorId: "102",
        recommendationReason: "New.",
        baseMentorId: "105",
      },
    };
    expect(shownRow(matchedItem, changes)).toMatchObject({
      menteeId: "201",
      mentorId: "102",
      recommendationReason: "New.",
    });
    expect(shownRow(unmatchedItem, changes).mentorId).toBeNull();
  });
});

describe("differsFromMatcher", () => {
  it("compares both the mentor and the reason", () => {
    const same = { mentorId: "101", recommendationReason: "Matcher reason." };
    expect(differsFromMatcher(same, matchedItem)).toBe(false);
    expect(differsFromMatcher({ ...same, mentorId: "102" }, matchedItem)).toBe(
      true,
    );
    expect(
      differsFromMatcher({ ...same, recommendationReason: "x" }, matchedItem),
    ).toBe(true);
    expect(
      differsFromMatcher(
        { mentorId: null, recommendationReason: "" },
        unmatchedItem,
      ),
    ).toBe(false);
  });
});

describe("mentorChoices", () => {
  it("lists the matcher's, the saved and each candidate once, scored from the candidates", () => {
    expect(mentorChoices(matchedItem)).toEqual([
      { userId: "101", name: "Ann Lee", score: null },
      { userId: "105", name: "Gil Ko", score: 0.3 },
      { userId: "102", name: "Dan Ma", score: 0.91 },
    ]);
    expect(mentorChoices(unmatchedItem)).toEqual([]);
  });
});

describe("slotsWithChanges", () => {
  const mentorSlots = [
    { userId: 101, name: "Ann Lee", slots: 2, assigned: 2 },
    { userId: 102, name: "Dan Ma", slots: 1, assigned: 0 },
  ];

  it("moves one mentee from the saved mentor to the chosen one", () => {
    const slots = slotsWithChanges(mentorSlots, {
      201: { mentorId: "102", recommendationReason: "", baseMentorId: "101" },
      203: { mentorId: "102", recommendationReason: "", baseMentorId: null },
      204: { mentorId: null, recommendationReason: "", baseMentorId: "101" },
      205: { mentorId: "101", recommendationReason: "x", baseMentorId: "101" },
    });
    expect(slots.get("101")).toEqual({
      name: "Ann Lee",
      slots: 2,
      assigned: 0,
    });
    expect(slots.get("102")).toEqual({ name: "Dan Ma", slots: 1, assigned: 2 });
  });

  it("leaves the overview's numbers alone", () => {
    slotsWithChanges(mentorSlots, {
      201: { mentorId: "102", recommendationReason: "", baseMentorId: "101" },
    });
    expect(mentorSlots[0].assigned).toBe(2);
  });
});

describe("mentorOptionLabel", () => {
  it("adds the free slots and the score", () => {
    expect(
      mentorOptionLabel(
        { userId: "102", name: "Dan Ma", score: 0.91234 },
        { slots: 2, assigned: 1 },
      ),
    ).toBe("Dan Ma (ID 102) — 1 of 2 slots free · 0.91");
  });

  it("leaves out what it does not have", () => {
    expect(mentorOptionLabel({ userId: "103", name: null, score: null })).toBe(
      "ID 103",
    );
  });
});

describe("problemText", () => {
  it("words each problem", () => {
    expect(
      problemText({
        code: "over_slots",
        mentor: { userId: 101, name: "Ann Lee" },
        assigned: 1,
        slots: 0,
      }),
    ).toBe("Ann Lee (ID 101) is given 1 mentee but has 0 slots this run.");
    expect(
      problemText({
        code: "reason_too_long",
        mentee: { userId: 201, name: null },
      }),
    ).toBe("The reason for ID 201 is over 300 characters.");
    expect(
      problemText({
        code: "no_reason",
        mentee: { userId: 201, name: "Cara Wang" },
      }),
    ).toBe("Cara Wang (ID 201) is matched with no reason.");
  });

  it("shows a code it does not know as is", () => {
    expect(problemText({ code: "something_new" })).toBe("something_new");
  });
});
