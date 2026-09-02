import { describe, it, expect, beforeEach } from "vitest";
import { Scorm12API } from "scorm-again";
import { toFlattenedCmi } from "@/training/scormBridge";

const LEARNER = { userId: 11, displayName: "Alice Admin" };
const SUSPEND = "x".repeat(1264);

describe("the behaviour a course depends on", () => {
  let api;

  beforeEach(() => {
    api = new Scorm12API({ autocommit: false, logLevel: 5 });
    api.loadFromFlattenedJSON(
      toFlattenedCmi(
        { suspendData: SUSPEND, lessonLocation: "Summary", lessonStatus: "incomplete" },
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

  it("reports a normal lesson mode", () => {
    // Empty here sends the driver down its invalid-mode branch.
    expect(api.lmsGetValue("cmi.core.lesson_mode")).toBe("normal");
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

    expect(JSON.stringify(payload)).toContain("passed");
  });
});
