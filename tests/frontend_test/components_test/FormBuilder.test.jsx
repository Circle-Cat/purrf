import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import FormBuilder from "@/components/recruiting/FormBuilder";

describe("FormBuilder", () => {
  it("adds a short-text field and emits schema with type:string", () => {
    const onChange = vi.fn();
    render(<FormBuilder schema={undefined} onChange={onChange} />);

    // Click "Add field" — default type is shortText
    fireEvent.click(screen.getByRole("button", { name: /add field/i }));

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls.at(-1)[0];
    expect(lastCall).toHaveProperty("type", "object");
    const keys = Object.keys(lastCall.properties ?? {});
    expect(keys).toHaveLength(1);
    expect(lastCall.properties[keys[0]]).toMatchObject({ type: "string" });
    // shortText has no x-widget and no enum
    expect(lastCall.properties[keys[0]]).not.toHaveProperty("x-widget");
    expect(lastCall.properties[keys[0]]).not.toHaveProperty("enum");
  });

  it("editing the title updates schema", () => {
    const onChange = vi.fn();
    render(<FormBuilder schema={undefined} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: /add field/i }));
    onChange.mockClear();

    const titleInput = screen.getByPlaceholderText(/field title/i);
    fireEvent.change(titleInput, { target: { value: "Full Name" } });

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls.at(-1)[0];
    const keys = Object.keys(lastCall.properties ?? {});
    expect(lastCall.properties[keys[0]]).toMatchObject({ title: "Full Name" });
  });

  it("deleting the only field leaves empty properties", () => {
    const onChange = vi.fn();
    render(<FormBuilder schema={undefined} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: /add field/i }));
    onChange.mockClear();

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls.at(-1)[0];
    expect(Object.keys(lastCall.properties ?? {})).toHaveLength(0);
  });
});
