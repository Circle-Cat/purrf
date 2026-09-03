import { describe, it, expect } from "vitest";
import {
  deriveEntry,
  toFlattenedCmi,
  isTrustedMessage,
  MESSAGE_TYPES,
} from "@/training/scormBridge";

const LEARNER = { userId: 11, displayName: "Alice Admin" };

describe("deriveEntry", () => {
  it("resumes when there is suspend data to resume from", () => {
    expect(deriveEntry({ suspendData: "x".repeat(1264) })).toBe("resume");
  });

  it("starts from the beginning when there is none", () => {
    expect(deriveEntry({ suspendData: null })).toBe("ab-initio");
    expect(deriveEntry({ suspendData: "" })).toBe("ab-initio");
    expect(deriveEntry({})).toBe("ab-initio");
  });
});

describe("toFlattenedCmi", () => {
  it("seeds the values a course reads in its first millisecond", () => {
    const cmi = toFlattenedCmi(
      {
        lessonStatus: "incomplete",
        lessonLocation: "Summary",
        suspendData: "blob",
        sessionTimeSeconds: 500,
      },
      LEARNER,
    );

    expect(cmi["cmi.core.lesson_location"]).toBe("Summary");
    expect(cmi["cmi.suspend_data"]).toBe("blob");
    expect(cmi["cmi.core.lesson_status"]).toBe("incomplete");
  });

  it("derives entry rather than expecting the caller to pass it", () => {
    expect(
      toFlattenedCmi({ suspendData: "blob" }, LEARNER)["cmi.core.entry"],
    ).toBe("resume");
    expect(toFlattenedCmi({}, LEARNER)["cmi.core.entry"]).toBe("ab-initio");
  });

  it("reports accumulated time as SCORM 1.2 CMITimespan", () => {
    const cmi = toFlattenedCmi({ sessionTimeSeconds: 500 }, LEARNER);

    expect(cmi["cmi.core.total_time"]).toBe("00:08:20");
  });

  it("says the lesson mode out loud", () => {
    // An empty string sends the driver down its invalid-mode branch.
    expect(toFlattenedCmi({}, LEARNER)["cmi.core.lesson_mode"]).toBe("normal");
  });

  it("carries the learner through, since a course displays the name", () => {
    const cmi = toFlattenedCmi({}, LEARNER);

    expect(cmi["cmi.core.student_id"]).toBe("11");
    expect(cmi["cmi.core.student_name"]).toBe("Alice Admin");
    expect(cmi["cmi.core.credit"]).toBe("credit");
  });

  it("starts an untouched assignment as not attempted", () => {
    expect(toFlattenedCmi({}, LEARNER)["cmi.core.lesson_status"]).toBe(
      "not attempted",
    );
  });

  it("seeds a stored score", () => {
    const cmi = toFlattenedCmi(
      { scoreRaw: "82.50", scoreMin: "0.00", scoreMax: "100.00" },
      LEARNER,
    );

    expect(cmi["cmi.core.score.raw"]).toBe("82.50");
    expect(cmi["cmi.core.score.min"]).toBe("0.00");
    expect(cmi["cmi.core.score.max"]).toBe("100.00");
  });

  it("starts an assignment with no score yet empty, not undefined", () => {
    const cmi = toFlattenedCmi({}, LEARNER);

    expect(cmi["cmi.core.score.raw"]).toBe("");
    expect(cmi["cmi.core.score.min"]).toBe("");
    expect(cmi["cmi.core.score.max"]).toBe("");
  });
});

describe("isTrustedMessage", () => {
  const origin = "https://test-training-content.purrf.io";

  it("accepts a message from the origin it was told to expect", () => {
    expect(
      isTrustedMessage(
        { origin, data: { type: MESSAGE_TYPES.COMMIT, cmi: {} } },
        origin,
      ),
    ).toBe(true);
  });

  it("rejects a commit carrying no cmi at all", () => {
    // Every reader of a commit iterates that object. Course content is
    // uploaded by third parties, so this arrives without a bug of ours.
    for (const cmi of [undefined, null, "x", 7, ["a"]]) {
      expect(
        isTrustedMessage(
          { origin, data: { type: MESSAGE_TYPES.COMMIT, cmi } },
          origin,
        ),
      ).toBe(false);
    }
  });

  it("still accepts the messages that carry no cmi by design", () => {
    for (const type of [MESSAGE_TYPES.READY, MESSAGE_TYPES.ERROR]) {
      expect(isTrustedMessage({ origin, data: { type } }, origin)).toBe(true);
    }
  });

  it("rejects any other origin", () => {
    // Without this, any page could post itself through the course.
    for (const forged of [
      "https://evil.example",
      "https://test.purrf.io",
      "https://test-training-content.purrf.io.evil.test",
      "null",
    ]) {
      expect(
        isTrustedMessage(
          { origin: forged, data: { type: MESSAGE_TYPES.COMMIT } },
          origin,
        ),
      ).toBe(false);
    }
  });

  it("accepts the player announcing itself", () => {
    // Every message the page acts on goes through here, the handshake
    // included, so a type missing from the table stalls the whole load.
    expect(
      isTrustedMessage({ origin, data: { type: MESSAGE_TYPES.READY } }, origin),
    ).toBe(true);
  });

  it("rejects anything that is not one of our messages", () => {
    expect(isTrustedMessage({ origin, data: null }, origin)).toBe(false);
    expect(isTrustedMessage({ origin, data: "commit" }, origin)).toBe(false);
    expect(
      isTrustedMessage({ origin, data: { type: "webpack:ok" } }, origin),
    ).toBe(false);
  });
});
