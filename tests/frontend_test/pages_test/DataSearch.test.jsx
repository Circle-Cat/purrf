import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom/vitest";
import DataSearch from "@/pages/DataSearch";

describe("DataSearch", () => {
  it("renders the DataSearch component correctly especially the search button", () => {
    render(<DataSearch />);

    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
    expect(screen.getByText("Data Search Page")).toBeInTheDocument();
  });
});
