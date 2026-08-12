import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ProfileSection from "@/pages/Profile/components/ProfileSection";

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

describe("ProfileSection", () => {
  it("fires onChange when a personal field is edited", () => {
    const onChange = vi.fn();
    render(<ProfileSection value={baseValue()} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/^First name/), {
      target: { value: "Ann" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        personal: expect.objectContaining({ firstName: "Ann" }),
      }),
    );
  });

  // First/last name and timezone are always required, whatever the posting's
  // profileConfig says; LinkedIn never is.
  it("marks first name, last name, and timezone required, but not LinkedIn", () => {
    render(<ProfileSection value={baseValue()} onChange={vi.fn()} />);
    const marked = (text) =>
      screen
        .getByText(text)
        .closest("label")
        .querySelector("span.text-red-500");
    expect(marked("First name")).toHaveTextContent("*");
    expect(marked("Last name")).toHaveTextContent("*");
    expect(marked("Timezone")).toHaveTextContent("*");
    expect(marked("LinkedIn")).toBeNull();
  });

  it("hides the education section when its requirement is off", () => {
    render(
      <ProfileSection
        value={baseValue()}
        onChange={vi.fn()}
        requirements={{ education: "off", experience: "optional" }}
      />,
    );
    // headings carry a trailing ReqMark, so match by prefix
    expect(screen.queryByText(/^Education/)).not.toBeInTheDocument();
    expect(screen.getByText(/^Experience/)).toBeInTheDocument();
  });

  it("appends an empty education row via onChange when Add is clicked", () => {
    const onChange = vi.fn();
    render(
      <ProfileSection
        value={baseValue()}
        onChange={onChange}
        requirements={{ education: "optional", experience: "off" }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /add education/i }));
    const next = onChange.mock.calls[0][0];
    expect(next.education).toHaveLength(1);
    expect(next.education[0].institution).toBe("");
  });
});

// Per-field education/experience editing is covered by the FormItem tests
// (Tasks 1-2); ProfileSection only needs to prove personal edits, requirement
// gating, and list add wiring.

describe("ProfileSection validation errors", () => {
  const errors = {
    "profile:firstName": "First name is required",
    "profile:timezone": "Timezone is required",
    "education:1:institution": "School is required",
    "experience:2:company": "Company is required",
  };

  const rows = () => ({
    personal: { firstName: "", lastName: "Wang", linkedin: "", timezone: "" },
    education: [{ id: 1, institution: "", degree: "", field: "" }],
    experience: [{ id: 2, title: "", company: "" }],
  });

  it("shows a personal field's message under that field", () => {
    render(
      <ProfileSection value={rows()} onChange={vi.fn()} errors={errors} />,
    );
    expect(screen.getByText("First name is required")).toBeInTheDocument();
    expect(screen.getByText("Timezone is required")).toBeInTheDocument();
  });

  it("says nothing about a personal field that is fine", () => {
    render(
      <ProfileSection value={rows()} onChange={vi.fn()} errors={errors} />,
    );
    expect(screen.queryByText("Last name is required")).not.toBeInTheDocument();
  });

  it("anchors every personal message so the form can scroll to it", () => {
    const { container } = render(
      <ProfileSection value={rows()} onChange={vi.fn()} errors={errors} />,
    );
    expect(
      container.querySelector('[data-error-key="profile:firstName"]'),
    ).toBeInTheDocument();
    expect(
      container.querySelector('[data-error-key="profile:timezone"]'),
    ).toBeInTheDocument();
  });

  it("outlines the control a personal message belongs to", () => {
    render(
      <ProfileSection value={rows()} onChange={vi.fn()} errors={errors} />,
    );
    // Token-wise, not substring-wise: `Input`'s own classes already include
    // `aria-invalid:border-destructive`, so a substring check can never fail.
    const classes = (label) =>
      screen.getByLabelText(label).className.split(/\s+/);
    expect(classes(/^First name/)).toContain("border-destructive");
    expect(classes(/^Last name/)).not.toContain("border-destructive");
  });

  it("passes each row its own namespaced errors", () => {
    const { container } = render(
      <ProfileSection
        value={rows()}
        onChange={vi.fn()}
        requirements={{ education: "required", experience: "required" }}
        errors={errors}
      />,
    );
    expect(screen.getByText("School is required")).toBeInTheDocument();
    expect(screen.getByText("Company is required")).toBeInTheDocument();
    expect(
      container.querySelector('[data-error-key="education:1:institution"]'),
    ).toBeInTheDocument();
    expect(
      container.querySelector('[data-error-key="experience:2:company"]'),
    ).toBeInTheDocument();
  });
});
