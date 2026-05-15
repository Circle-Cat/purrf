import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import TimezoneSelector from "@/components/common/TimezoneSelector";

vi.mock("@/constants/Timezones", () => ({
  default: {
    "America/New_York": "Eastern Time (US & Canada)",
    "America/Los_Angeles": "Pacific Time (US & Canada)",
  },
}));

describe("TimezoneSelector", () => {
  it("displays the timezone label when labelSource is 'value' (default)", () => {
    render(<TimezoneSelector value="America/New_York" onChange={() => {}} />);
    expect(
      screen.getByText(/Eastern Time \(US & Canada\)/),
    ).toBeInTheDocument();
  });

  it("displays the IANA key when labelSource is 'key'", () => {
    render(
      <TimezoneSelector
        value="America/New_York"
        onChange={() => {}}
        labelSource="key"
      />,
    );
    expect(screen.getByText("America/New_York")).toBeInTheDocument();
  });

  it("disables the selector when isDisabled is true", () => {
    render(
      <TimezoneSelector
        value="America/New_York"
        onChange={() => {}}
        isDisabled
      />,
    );
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
