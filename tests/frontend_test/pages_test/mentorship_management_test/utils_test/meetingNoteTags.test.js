import { describe, it, expect } from "vitest";
import {
  getDisabledNoteTags,
  hasAbsentTag,
} from "@/pages/MentorshipManagement/utils/meetingNoteTags";

describe("hasAbsentTag", () => {
  it("is false when no absent tag is selected", () => {
    expect(hasAbsentTag(["mentor_late"])).toBe(false);
  });

  it("is true when any absent tag is selected", () => {
    expect(hasAbsentTag(["unknown_absent"])).toBe(true);
  });
});

describe("getDisabledNoteTags", () => {
  it("disables nothing when no tags are selected", () => {
    expect(getDisabledNoteTags([])).toEqual(new Set());
  });

  it("disables the other absent tags once one absent tag is selected", () => {
    expect(getDisabledNoteTags(["unknown_absent"])).toEqual(
      new Set(["mentor_absent", "mentee_absent"]),
    );
  });

  it("disables the same role's late tag when absent is selected", () => {
    const disabled = getDisabledNoteTags(["mentor_absent"]);

    expect(disabled.has("mentor_late")).toBe(true);
    expect(disabled.has("mentee_late")).toBe(false);
  });

  it("disables the same role's absent tag when late is selected", () => {
    const disabled = getDisabledNoteTags(["mentee_late"]);

    expect(disabled.has("mentee_absent")).toBe(true);
    expect(disabled.has("mentor_absent")).toBe(false);
  });

  it("disables unknown_late once a specific late tag is selected, but not the other specific late tag (mentor/mentee late may coexist)", () => {
    const disabled = getDisabledNoteTags(["mentor_late"]);
    expect(disabled.has("unknown_late")).toBe(true);
    expect(disabled.has("mentee_late")).toBe(false);
  });

  it("disables both specific late tags once unknown_late is selected", () => {
    expect(getDisabledNoteTags(["unknown_late"])).toEqual(
      new Set(["mentor_late", "mentee_late"]),
    );
  });

  it("disables all absent tags when isCompleted is true, even with none selected", () => {
    expect(getDisabledNoteTags([], { isCompleted: true })).toEqual(
      new Set(["unknown_absent", "mentor_absent", "mentee_absent"]),
    );
  });

  it("does not disable absent tags when isCompleted is false", () => {
    expect(getDisabledNoteTags([], { isCompleted: false })).toEqual(new Set());
  });
});
