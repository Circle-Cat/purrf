import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import AttendanceMark from "@/pages/MentorshipManagement/components/AttendanceMark";

describe("AttendanceMark", () => {
  it("is a red ! that names every flagged meeting and lists them on focus", async () => {
    const lines = [
      "2026-08-30: Erin Ma absent",
      "2026-09-06: Erin Ma late arrival",
    ];
    render(<AttendanceMark lines={lines} />);

    const mark = screen.getByRole("button", {
      name: "Attendance issues: 2026-08-30: Erin Ma absent, 2026-09-06: Erin Ma late arrival",
    });
    expect(mark).toHaveTextContent("!");

    await userEvent.tab();
    expect(
      (await screen.findAllByText("2026-09-06: Erin Ma late arrival")).length,
    ).toBeGreaterThan(0);
  });
});
