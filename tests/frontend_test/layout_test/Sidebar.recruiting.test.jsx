import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/context/auth", () => ({
  useAuth: () => ({ permissions: ["recruiting.job.write"] }),
}));

import Sidebar from "@/components/layout/Sidebar";

describe("Sidebar recruiting entries", () => {
  it("shows Recruiting when the user has job.write", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("Recruiting")).toBeInTheDocument();
  });

  it("hides My Reviews without job.approve", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(screen.queryByText("My Reviews")).not.toBeInTheDocument();
  });
});
