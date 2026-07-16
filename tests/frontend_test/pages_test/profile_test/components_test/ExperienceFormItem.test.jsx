import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ExperienceFormItem from "@/pages/Profile/components/ExperienceFormItem";

const item = {
  id: 2,
  title: "",
  company: "",
  isCurrentlyWorking: false,
  startMonth: "",
  startYear: "",
  endMonth: "",
  endYear: "",
};

describe("ExperienceFormItem", () => {
  it("fires onChange for the title input", () => {
    const onChange = vi.fn();
    render(
      <ExperienceFormItem
        item={item}
        errors={{}}
        onChange={onChange}
        onDelete={vi.fn()}
      />,
    );
    fireEvent.change(screen.getAllByRole("textbox")[0], {
      target: { value: "Engineer" },
    });
    expect(onChange).toHaveBeenCalledWith(2, "title", "Engineer");
  });

  it("fires onChange(id, 'isCurrentlyWorking', true) when the checkbox is ticked", () => {
    const onChange = vi.fn();
    render(
      <ExperienceFormItem
        item={item}
        errors={{}}
        onChange={onChange}
        onDelete={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(2, "isCurrentlyWorking", true);
  });

  it("disables the end-date selects when currently working", () => {
    render(
      <ExperienceFormItem
        item={{ ...item, isCurrentlyWorking: true }}
        errors={{}}
        onChange={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    const selects = screen.getAllByRole("combobox");
    // end month/year are the last two selects
    expect(selects[selects.length - 1]).toBeDisabled();
    expect(selects[selects.length - 2]).toBeDisabled();
  });
});
