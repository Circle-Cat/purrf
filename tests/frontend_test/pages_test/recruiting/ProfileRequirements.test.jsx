import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ProfileRequirements from "@/pages/Recruiting/components/ProfileRequirements";

describe("ProfileRequirements", () => {
  it("shows Required and Optional badges and omits off/missing", () => {
    render(
      <ProfileRequirements
        profileConfig={{
          education: "required",
          workExperience: "optional",
          resume: "off",
        }}
      />,
    );
    expect(screen.getByText("Education")).toBeInTheDocument();
    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.getByText("Work experience")).toBeInTheDocument();
    expect(screen.getByText("Optional")).toBeInTheDocument();
    expect(screen.queryByText("Resume")).not.toBeInTheDocument();
  });

  it("renders nothing when no section is required or optional", () => {
    const { container } = render(
      <ProfileRequirements profileConfig={{ education: "off" }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
