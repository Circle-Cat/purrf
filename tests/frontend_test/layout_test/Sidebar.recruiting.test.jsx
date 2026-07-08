import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/context/auth", () => ({
  useAuth: () => ({ permissions: ["recruiting.job.write"] }),
}));

import Sidebar from "@/components/layout/Sidebar";

describe("Sidebar recruiting entries", () => {
  it("shows Job Postings when the user has job.write", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("Job Postings")).toBeInTheDocument();
  });

  it("hides My Posting Reviews without job.approve", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(screen.queryByText("My Posting Reviews")).not.toBeInTheDocument();
  });

  it("shows My Interview Evaluations for any logged-in user regardless of permissions", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("My Interview Evaluations")).toBeInTheDocument();
  });
});
