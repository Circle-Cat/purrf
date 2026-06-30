import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JobBasicsSection from "@/pages/Recruiting/postings/JobBasicsSection";

describe("JobBasicsSection", () => {
  const props = { title: "", description: "", kind: "activity" };

  it("emits title changes", () => {
    const onChange = vi.fn();
    render(<JobBasicsSection {...props} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE" },
    });
    expect(onChange).toHaveBeenCalledWith({ title: "SWE" });
  });

  it("emits kind changes via the Select", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JobBasicsSection {...props} onChange={onChange} />);
    await user.click(screen.getByRole("combobox", { name: "Kind" }));
    await user.click(screen.getByRole("option", { name: "Employment" }));
    expect(onChange).toHaveBeenCalledWith({ kind: "employment" });
  });

  it("emits description changes", () => {
    const onChange = vi.fn();
    render(<JobBasicsSection {...props} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Test description" },
    });
    expect(onChange).toHaveBeenCalledWith({ description: "Test description" });
  });

  it("renders description field empty when description is undefined", () => {
    const onChange = vi.fn();
    const propsWithUndef = { ...props, description: undefined };
    render(<JobBasicsSection {...propsWithUndef} onChange={onChange} />);
    const descField = screen.getByLabelText("Description");
    expect(descField.value).toBe("");
  });
});
