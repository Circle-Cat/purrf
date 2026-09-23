import { afterEach, describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PrototypeSwitcher from "@/PrototypeSwitcher";

afterEach(() => {
  window.history.replaceState(null, "", window.location.pathname);
});

describe("PrototypeSwitcher", () => {
  it("keeps a prototype's own deep link on that prototype", () => {
    window.history.replaceState(null, "", "#mentorship/pairs/502");
    render(<PrototypeSwitcher />);

    expect(screen.getByText("Mentorship management")).toBeInTheDocument();
    expect(screen.getByText("Meeting log")).toBeInTheDocument();
  });

  it("opens a filtered list from a shared link", () => {
    window.history.replaceState(null, "", "#mentorship?q=Bob");
    render(<PrototypeSwitcher />);

    expect(screen.getByRole("button", { name: "Bob Liu" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cara Wang" })).toBeNull();
  });
});
