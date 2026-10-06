import { describe, it, expect } from "vitest";
import {
  checkedLabels,
  personWithId,
  scoreLabel,
  surveyLabel,
} from "@/pages/MentorshipManagement/utils/matchingLabels";

describe("surveyLabel", () => {
  it("maps a code to its label", () => {
    expect(surveyLabel("careerTransition", "via_work_experience")).toBe(
      "Via work experience",
    );
    expect(surveyLabel("transitionType", "considering_transition")).toBe(
      "Considering a transition",
    );
    expect(surveyLabel("externalMentoringExp", "3_plus")).toBe("3+");
    expect(surveyLabel("urgency", "no_timeline")).toBe("No timeline");
    expect(surveyLabel("menteeStage", "grad_planning")).toBe(
      "Planning after graduation",
    );
  });

  it("adds the person's own words after the label", () => {
    expect(surveyLabel("jobMarketRegion", "china", "Shenzhen")).toBe(
      "China (Shenzhen)",
    );
  });

  it("falls back to the code it does not know", () => {
    expect(surveyLabel("urgency", "2y")).toBe("2y");
  });

  it("is null with no answer, unless there are own words", () => {
    expect(surveyLabel("urgency", null)).toBeNull();
    expect(surveyLabel("developmentRegion", null, "Europe")).toBe("Europe");
  });
});

describe("checkedLabels", () => {
  it("lists the labels of the keys set to true, in order", () => {
    expect(
      checkedLabels("skills", {
        soft_skills: true,
        networking: false,
        industry_trends: true,
        made_up: true,
      }),
    ).toEqual(["Soft skills", "Industry trends", "made_up"]);
  });

  it("is empty for no answer", () => {
    expect(checkedLabels("specificIndustry", null)).toEqual([]);
  });
});

describe("personWithId", () => {
  it("puts the ID beside the name, or stands alone without one", () => {
    expect(personWithId({ userId: 4, name: "Ann Lee" })).toBe("Ann Lee (ID 4)");
    expect(personWithId({ userId: 5, name: null })).toBe("ID 5");
  });
});

describe("scoreLabel", () => {
  it("rounds to two places and dashes a missing score", () => {
    expect(scoreLabel(0.87642)).toBe("0.88");
    expect(scoreLabel(12)).toBe("12");
    expect(scoreLabel(0)).toBe("0");
    expect(scoreLabel(null)).toBe("—");
  });
});
