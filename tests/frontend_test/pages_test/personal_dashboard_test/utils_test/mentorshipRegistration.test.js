import { describe, it, expect } from "vitest";
import {
  INDUSTRY_CONFIG,
  SKILLSET_CONFIG,
  mapRegistrationToForm,
  mapFormToApi,
} from "@/pages/PersonalDashboard/utils/mentorshipRegistration";

describe("mentorshipRegistration utils", () => {
  describe("mapRegistrationToForm", () => {
    it("maps backend registration data to form state correctly", () => {
      const registration = {
        globalPreferences: {
          specificIndustry: {
            swe: true,
            uiux: false,
          },
          skillsets: {
            resumeGuidance: true,
            networking: true,
          },
        },
        roundPreferences: {
          maxPartners: 2,
          goal: "Improve leadership skills",
          expectedPartnerIds: ["1"],
          unexpectedPartnerIds: ["2"],
        },
      };

      const allPastPartners = [
        { id: "1", preferredName: "Alice" },
        { id: "2", firstName: "Bob", lastName: "Smith" },
      ];

      const result = mapRegistrationToForm(registration, allPastPartners);

      expect(result.industries).toEqual([
        INDUSTRY_CONFIG.find((c) => c.id === "swe"),
      ]);

      expect(result.skillsets).toEqual(
        SKILLSET_CONFIG.filter((c) =>
          ["resumeGuidance", "networking"].includes(c.id),
        ),
      );

      expect(result.partnerCapacity).toBe(2);
      expect(result.goal).toBe("Improve leadership skills");

      expect(result.selectedPartners).toEqual([{ id: "1", name: "Alice" }]);

      expect(result.excludedPartners).toEqual([{ id: "2", name: "Bob Smith" }]);
    });

    it("returns safe default values when preferences are missing", () => {
      const registration = {};
      const allPastPartners = [];

      const result = mapRegistrationToForm(registration, allPastPartners);

      expect(result.industries).toEqual([]);
      expect(result.skillsets).toEqual([]);
      expect(result.partnerCapacity).toBe(1);
      expect(result.goal).toBe("");
      expect(result.selectedPartners).toEqual([]);
      expect(result.excludedPartners).toEqual([]);
    });
  });

  describe("mapFormToApi", () => {
    it("maps form state back to API format correctly", () => {
      const formData = {
        industries: [{ id: "ds" }],
        skillsets: [{ id: "leadership" }, { id: "communicationSkills" }],
        partnerCapacity: 3,
        goal: "Become a better mentor",
        selectedPartners: [{ id: "10" }, { id: "11" }],
        excludedPartners: [{ id: "20" }],
      };

      const currentRegistration = {
        id: "reg-1",
        globalPreferences: {},
        roundPreferences: {},
      };

      const result = mapFormToApi(formData, currentRegistration);

      // Industry boolean map
      expect(result.globalPreferences.specificIndustry).toEqual(
        INDUSTRY_CONFIG.reduce(
          (acc, c) => ({
            ...acc,
            [c.id]: c.id === "ds",
          }),
          {},
        ),
      );

      // Skillset boolean map
      expect(result.globalPreferences.skillsets).toEqual(
        SKILLSET_CONFIG.reduce(
          (acc, c) => ({
            ...acc,
            [c.id]: ["leadership", "communicationSkills"].includes(c.id),
          }),
          {},
        ),
      );

      expect(result.roundPreferences.maxPartners).toBe(3);
      expect(result.roundPreferences.goal).toBe("Become a better mentor");
      expect(result.roundPreferences.expectedPartnerIds).toEqual(["10", "11"]);
      expect(result.roundPreferences.unexpectedPartnerIds).toEqual(["20"]);
    });

    it("preserves existing registration fields when mapping", () => {
      const formData = {
        industries: [],
        skillsets: [],
        partnerCapacity: 1,
        goal: "",
        selectedPartners: [],
        excludedPartners: [],
      };

      const currentRegistration = {
        id: "existing-id",
        globalPreferences: { foo: "bar" },
        roundPreferences: { baz: "qux" },
      };

      const result = mapFormToApi(formData, currentRegistration);

      expect(result.id).toBe("existing-id");
      expect(result.globalPreferences.foo).toBe("bar");
      expect(result.roundPreferences.baz).toBe("qux");
    });
  });
});
