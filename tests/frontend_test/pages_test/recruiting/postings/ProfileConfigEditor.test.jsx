import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProfileConfigEditor from "@/pages/Recruiting/postings/ProfileConfigEditor";

describe("ProfileConfigEditor", () => {
  it("defaults missing fields to optional", () => {
    render(<ProfileConfigEditor value={{}} onChange={() => {}} />);
    // the 'optional' radio of each row is checked by default
    expect(
      screen.getByRole("radio", { name: "Education optional" }),
    ).toBeChecked();
  });

  it("emits a changed requirement level", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ProfileConfigEditor
        value={{
          education: "optional",
          workExperience: "optional",
          resume: "optional",
        }}
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole("radio", { name: "Resume required" }));
    expect(onChange).toHaveBeenCalledWith({
      education: "optional",
      workExperience: "optional",
      resume: "required",
    });
  });
});
