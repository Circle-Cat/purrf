import { describe, it, expect, beforeEach } from "vitest";
import { Scorm12API } from "scorm-again";
import { toFlattenedCmi } from "@/training/scormBridge";

const LEARNER = { userId: 11, displayName: "Alice Admin" };
const SUSPEND = "x".repeat(1264);

// The player (backend/training/player/player.html) constructs Scorm12API
// with exactly these options. Without dataCommitFormat: "flattened" here,
// renderCommitCMI returns the library's default nested {cmi: {core: {...}}}
// shape instead of flat "cmi.core.*" dot-keys, and the mismatch would not
// show up here -- only in training_progress_service.py, which reads flat
// keys and would silently store nothing.
const API_OPTIONS = {
  autocommit: false,
  logLevel: 5,
  dataCommitFormat: "flattened",
};

describe("the behaviour a course depends on", () => {
  let api;

  beforeEach(() => {
    api = new Scorm12API(API_OPTIONS);
    api.loadFromFlattenedJSON(
      toFlattenedCmi(
        {
          suspendData: SUSPEND,
          lessonLocation: "Summary",
          lessonStatus: "incomplete",
        },
        LEARNER,
      ),
    );
    api.lmsInitialize();
  });

  it("hands back stored progress on the very first read", () => {
    // The course reads both in the same millisecond as LMSInitialize.
    expect(api.lmsGetValue("cmi.suspend_data")).toBe(SUSPEND);
    expect(api.lmsGetValue("cmi.core.lesson_location")).toBe("Summary");
  });

  it("says the entry is a resume", () => {
    expect(api.lmsGetValue("cmi.core.entry")).toBe("resume");
  });

  it("accepts an empty suspend_data as a real write", () => {
    // The course clears it to reset itself, and reads the return value to
    // find out whether the reset worked. "false" makes it run degraded.
    expect(api.lmsSetValue("cmi.suspend_data", "")).toBe("true");
    expect(api.lmsSetValue("cmi.core.lesson_location", "")).toBe("true");
  });

  it("stores suspend_data well past the 4096 the specification allows", () => {
    const long = "y".repeat(40000);

    expect(api.lmsSetValue("cmi.suspend_data", long)).toBe("true");
    expect(api.lmsGetValue("cmi.suspend_data")).toBe(long);
  });

  it("answers an unimplemented element with an empty string, not an exception", () => {
    // Courses probe optional elements; a throw takes the whole course down.
    expect(() => api.lmsGetValue("cmi.interactions._count")).not.toThrow();
    expect(api.lmsGetValue("cmi.interactions.0.id")).toBe("");
  });

  it("renders a commit payload carrying what the course wrote", () => {
    api.lmsSetValue("cmi.core.lesson_status", "passed");
    api.lmsSetValue("cmi.core.session_time", "00:02:30");

    const payload = api.renderCommitCMI(true);

    // The backend reads flat "cmi.core.*" keys, not the library's default
    // nested shape -- a nested payload already shipped once on this branch.
    expect(payload["cmi.core.lesson_status"]).toBe("passed");
  });

  it("keeps a seeded total_time until this session adds to it", () => {
    // training_progress_service.py replaces rather than accumulates
    // session_time_seconds on the strength of this: getCurrentTotalTime()
    // returns the seeded total plus wall time since init, which only holds
    // if loadFromFlattenedJSON actually applies total_time before init.
    const seeded = new Scorm12API(API_OPTIONS);
    seeded.loadFromFlattenedJSON(
      toFlattenedCmi({ sessionTimeSeconds: 500 }, LEARNER),
    );
    seeded.lmsInitialize();

    const payload = seeded.renderCommitCMI(true);

    expect(payload["cmi.core.total_time"]).toMatch(/^00:08:20(\.\d+)?$/);
  });
});
