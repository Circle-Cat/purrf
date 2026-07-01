import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthContext } from "@/context/auth";
import RecruitingProfileForm from "@/pages/Recruiting/components/RecruitingProfileForm";

const renderForm = (profileConfig, email = "applicant@example.com") =>
  render(
    <AuthContext.Provider value={{ user: email ? { email } : null }}>
      <RecruitingProfileForm profileConfig={profileConfig} />
    </AuthContext.Provider>,
  );

describe("RecruitingProfileForm", () => {
  it("renders a read-only contact email from the logged-in account", () => {
    renderForm({});
    const email = screen.getByLabelText("Contact email");
    expect(email).toHaveValue("applicant@example.com");
    expect(email).toHaveAttribute("readonly");
  });

  it("always renders basic info even when every section is off", () => {
    renderForm({ education: "off", workExperience: "off", resume: "off" });
    expect(screen.getByLabelText("First name")).toBeInTheDocument();
  });

  it("hides the resume upload when resume is off", () => {
    renderForm({ resume: "off" });
    expect(
      screen.queryByRole("heading", { name: /resume/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the resume upload with a required marker when resume is required", () => {
    renderForm({ resume: "required" });
    expect(
      screen.getByRole("heading", { name: /resume/i }),
    ).toBeInTheDocument();
  });

  it("renders the education block with an entry and add control when required", () => {
    renderForm({ education: "required" });
    expect(
      screen.getByRole("heading", { name: /education/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add education" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/School/)).toBeInTheDocument();
  });

  it("hides the education block when education is off", () => {
    renderForm({ education: "off" });
    expect(
      screen.queryByRole("heading", { name: /education/i }),
    ).not.toBeInTheDocument();
  });

  it("renders the work-experience block with an add control when required", () => {
    renderForm({ workExperience: "required" });
    expect(
      screen.getByRole("heading", { name: /experience/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add experience" }),
    ).toBeInTheDocument();
  });
});
