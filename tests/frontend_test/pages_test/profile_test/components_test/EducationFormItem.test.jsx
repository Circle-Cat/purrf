import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import EducationFormItem from "@/pages/Profile/components/EducationFormItem";

const item = {
  id: 1,
  institution: "",
  degree: "",
  field: "",
  startMonth: "",
  startYear: "",
  endMonth: "",
  endYear: "",
};

describe("EducationFormItem", () => {
  it("fires onChange with (id, field, value) when the school input changes", () => {
    const onChange = vi.fn();
    render(
      <EducationFormItem
        item={item}
        errors={{}}
        onChange={onChange}
        onDelete={vi.fn()}
      />,
    );
    // School is the first text input (degree is a <select>, not a textbox)
    fireEvent.change(screen.getAllByRole("textbox")[0], {
      target: { value: "x" },
    });
    expect(onChange).toHaveBeenCalledWith(1, "institution", "x");
  });

  it("renders a validation error for a field", () => {
    render(
      <EducationFormItem
        item={item}
        errors={{ "1-institution": "School is required" }}
        onChange={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("School is required")).toBeInTheDocument();
  });

  it("fires onDelete with the item id", () => {
    const onDelete = vi.fn();
    render(
      <EducationFormItem
        item={item}
        errors={{}}
        onChange={vi.fn()}
        onDelete={onDelete}
      />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onDelete).toHaveBeenCalledWith(1);
  });
});
