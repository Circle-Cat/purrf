// tests/frontend_test/pages_test/profile_test/components_test/ResumePrefilledProfileSection.test.jsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ResumePrefilledProfileSection from "@/pages/Profile/components/ResumePrefilledProfileSection";

// Stub ResumeUpload with a button that emits a fixed ParsedResume.
const PARSED = {
  user: {
    firstName: "Ann",
    lastName: "Liu",
    linkedinLink: "https://linkedin.com/in/annliu",
    timezoneSuggestion: "",
  },
  education: [],
  workHistory: [],
  projects: [],
  unmapped: {},
};
vi.mock("@/components/common/ResumeUpload", () => ({
  default: ({ onParsed }) => (
    <button type="button" onClick={() => onParsed(PARSED)}>
      mock-upload
    </button>
  ),
}));
vi.mock("@/components/common/TimezoneSelector", () => ({
  default: ({ value, onChange }) => (
    <input
      aria-label="timezone"
      value={value || ""}
      onChange={(e) => onChange({ value: e.target.value })}
    />
  ),
}));

const baseValue = () => ({
  personal: { firstName: "", lastName: "", linkedin: "", timezone: "" },
  education: [],
  experience: [],
});

describe("ResumePrefilledProfileSection", () => {
  it("merges a parsed resume into the value via onChange", () => {
    const onChange = vi.fn();
    render(
      <ResumePrefilledProfileSection value={baseValue()} onChange={onChange} />,
    );
    fireEvent.click(screen.getByText("mock-upload"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        personal: expect.objectContaining({
          firstName: "Ann",
          lastName: "Liu",
          linkedin: "https://linkedin.com/in/annliu",
        }),
      }),
    );
  });

  it("renders the ProfileSection (personal fields visible)", () => {
    render(
      <ResumePrefilledProfileSection value={baseValue()} onChange={vi.fn()} />,
    );
    expect(screen.getByLabelText("First name")).toBeInTheDocument();
  });
});
