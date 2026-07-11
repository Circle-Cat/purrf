import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

let mockPermissions = ["recruiting.job.write"];
vi.mock("@/context/auth", () => ({
  useAuth: () => ({ permissions: mockPermissions }),
}));

import Sidebar from "@/components/layout/Sidebar";

describe("Sidebar recruiting entries", () => {
  beforeEach(() => {
    mockPermissions = ["recruiting.job.write"];
  });

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

  it("hides My Interview Evaluations without recruiting.interview.evaluate", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(
      screen.queryByText("My Interview Evaluations"),
    ).not.toBeInTheDocument();
  });

  it("shows My Interview Evaluations with recruiting.interview.evaluate", () => {
    mockPermissions = ["recruiting.interview.evaluate"];
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("My Interview Evaluations")).toBeInTheDocument();
  });
});
