import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import PendingApprovalsCard from "@/pages/MentorshipManagement/components/PendingApprovalsCard";

const Where = () => {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
};

const REQUESTS = [
  {
    requestId: 31,
    action: "publish_matching",
    round: { roundId: 7, name: "Spring 2026" },
    person: null,
    raisedBy: { userId: 9, name: "Ada Ng" },
    reason: "Reviewed every pair",
    createdAt: "2026-10-07T09:30:00+00:00",
  },
  {
    requestId: 32,
    action: "exempt_matching",
    round: { roundId: 7, name: "Spring 2026" },
    person: { userId: 21, name: "Ann Lee" },
    raisedBy: { userId: 9, name: "Ada Ng" },
    reason: "Her mentor left",
    createdAt: "2026-10-07T10:00:00+00:00",
  },
];

const renderCard = (requests) =>
  render(
    <MemoryRouter initialEntries={["/mentorship-management"]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <PendingApprovalsCard requests={requests} />
              <Where />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );

describe("PendingApprovalsCard", () => {
  it("lists each request with what it asks, who sent it and why", () => {
    renderCard(REQUESTS);

    expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    expect(screen.getByText("2 waiting")).toBeInTheDocument();
    expect(
      screen.getByText("Publish matching result · Spring 2026"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Matching exemption · Spring 2026 · Ann Lee"),
    ).toBeInTheDocument();
    expect(screen.getByText("Her mentor left")).toBeInTheDocument();
    expect(screen.getAllByText(/^From Ada Ng/)).toHaveLength(2);
  });

  it("opens the round's matching results to review a publish request", async () => {
    const user = userEvent.setup();
    renderCard(REQUESTS);

    await user.click(screen.getAllByRole("button", { name: "Review" })[0]);

    expect(screen.getByTestId("where")).toHaveTextContent(
      "/mentorship-management/matching/7",
    );
  });

  it("opens the Needs exemption list at the person to review an exemption", async () => {
    const user = userEvent.setup();
    renderCard(REQUESTS);

    await user.click(screen.getAllByRole("button", { name: "Review" })[1]);

    expect(screen.getByTestId("where")).toHaveTextContent(
      "/mentorship-management?round=7&needsExemption=1&id=21",
    );
  });

  it("renders nothing with nothing waiting", () => {
    renderCard([]);

    expect(screen.queryByText("Pending approvals")).not.toBeInTheDocument();
  });
});
