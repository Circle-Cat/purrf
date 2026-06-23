import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import JsonSchemaForm from "@/components/recruiting/JsonSchemaForm";
import { validate } from "@/components/recruiting/jsonSchemaUtils";

const schema = {
  type: "object",
  required: ["why"],
  properties: {
    why: { type: "string", title: "Why mentor?" },
    bio: { type: "string", title: "Bio", "x-widget": "textarea" },
    level: { type: "string", title: "Level", enum: ["Junior", "Senior"] },
  },
};

describe("JsonSchemaForm", () => {
  it("renders a field per property with its title", () => {
    render(<JsonSchemaForm schema={schema} value={{}} onChange={() => {}} />);
    expect(screen.getByText("Why mentor?")).toBeInTheDocument();
    expect(screen.getByText("Level")).toBeInTheDocument();
  });
  it("calls onChange when a text field changes", () => {
    const onChange = vi.fn();
    render(<JsonSchemaForm schema={schema} value={{}} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Why mentor?"), {
      target: { value: "exp" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ why: "exp" }),
    );
  });
  it("validate flags missing required fields", () => {
    expect(validate(schema, {})).toHaveProperty("why");
    expect(validate(schema, { why: "x" })).toEqual({});
  });
});
