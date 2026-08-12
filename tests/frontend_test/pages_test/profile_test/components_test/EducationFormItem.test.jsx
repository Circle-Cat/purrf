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

describe("EducationFormItem error keys", () => {
  it("reads errors keyed `${id}-${field}` when no key builder is given", () => {
    // The Profile edit modals key errors this way and must keep working.
    const { container } = render(
      <EducationFormItem
        item={item}
        errors={{ "1-institution": "School is required" }}
        onChange={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("School is required")).toBeInTheDocument();
    expect(
      container.querySelector('[data-error-key="1-institution"]'),
    ).toBeInTheDocument();
  });

  it("reads errors under whatever key the caller builds", () => {
    const { container } = render(
      <EducationFormItem
        item={item}
        errors={{ "education:1:degree": "Degree is required" }}
        errorKeyFor={(field) => `education:${item.id}:${field}`}
        onChange={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("Degree is required")).toBeInTheDocument();
    expect(
      container.querySelector('[data-error-key="education:1:degree"]'),
    ).toBeInTheDocument();
  });
});
