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
    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "Ann" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        personal: expect.objectContaining({ firstName: "Ann" }),
      }),
    );
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
