import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import BackToBoardLink from "@/pages/Recruiting/applications/BackToBoardLink";

/** The component renders a <Link>, so it needs a router context. */
const renderLink = (props) =>
  render(
    <MemoryRouter>
      <BackToBoardLink {...props} />
    </MemoryRouter>,
  );

describe("BackToBoardLink", () => {
  it("sends an owner back to their board, carrying the job and the applicant to focus", () => {
    renderLink({
      jobId: 7,
      applicationId: "101",
      evaluatorMode: false,
      canView: true,
    });
    expect(
      screen.getByRole("link", { name: "Applications Board" }),
    ).toHaveAttribute("href", "/recruiting/board?jobId=7&focus=101");
  });

  it("sends an evaluator back to My Evaluations, not to a board they may not own", () => {
    renderLink({
      jobId: 7,
      applicationId: "101",
      evaluatorMode: true,
      canView: true,
    });
    expect(
      screen.getByRole("link", { name: "My Evaluations" }),
    ).toHaveAttribute("href", "/recruiting/my-evaluations");
    expect(
      screen.queryByRole("link", { name: "Applications Board" }),
    ).not.toBeInTheDocument();
  });

  it("renders nothing for a viewer with no board to go back to", () => {
    // A pure current-stage assignee outside evaluate mode: the board is
    // gated on owner-or-read.all, so a link would only strand them on
    // "You don't own any postings."
    const { container } = renderLink({
      jobId: 7,
      applicationId: "101",
      evaluatorMode: false,
      canView: false,
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the job id is unknown, rather than a link to a broken board", () => {
    const { container } = renderLink({
      jobId: null,
      applicationId: "101",
      evaluatorMode: false,
      canView: true,
    });
    expect(container).toBeEmptyDOMElement();
  });
});
