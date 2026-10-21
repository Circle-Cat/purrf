import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MarkBadges from "@/pages/MentorshipManagement/components/MarkBadges";

describe("MarkBadges", () => {
  it("shows nothing without marks", () => {
    const { container } = render(<MarkBadges />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows one badge per kind and counts repeats", () => {
    render(<MarkBadges noShow={2} redFlag={1} />);
    expect(screen.getByText("No show ×2")).toBeInTheDocument();
    expect(screen.getByText("Red flag")).toBeInTheDocument();
  });

  it("drops a kind with no marks", () => {
    render(<MarkBadges noShow={1} redFlag={0} />);
    expect(screen.getByText("No show")).toBeInTheDocument();
    expect(screen.queryByText(/Red flag/)).not.toBeInTheDocument();
  });
});
