import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import Blacklist from "@/pages/Recruiting/Blacklist";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

const entry = {
  userId: 1,
  name: "Sam Rivera",
  email: "sam@example.com",
  reason: "Submitted AI-generated answers.",
  blockedAt: "2026-06-10T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listBlacklist.mockResolvedValue({ data: [entry] });
  api.unblockUser.mockResolvedValue({ data: {} });
});

describe("Blacklist page", () => {
  it("loads and lists blocked users on mount", async () => {
    render(<Blacklist />);
    expect(await screen.findByText("Sam Rivera")).toBeInTheDocument();
    expect(api.listBlacklist).toHaveBeenCalledWith(undefined);
  });

  it("shows the empty state when there are no blocked users", async () => {
    api.listBlacklist.mockResolvedValue({ data: [] });
    render(<Blacklist />);
    expect(
      await screen.findByText(/No blocked users\. Blacklist someone/),
    ).toBeInTheDocument();
  });

  it("searches by the typed query on Enter and shows a no-match empty state", async () => {
    render(<Blacklist />);
    await screen.findByText("Sam Rivera");
    api.listBlacklist.mockResolvedValue({ data: [] });

    fireEvent.change(screen.getByPlaceholderText(/Search by name/), {
      target: { value: "nomatch" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Search by name/), {
      key: "Enter",
    });

    expect(
      await screen.findByText("No blocked users match this search."),
    ).toBeInTheDocument();
    expect(api.listBlacklist).toHaveBeenCalledWith("nomatch");
  });

  it("unblocks a user after confirming the dialog", async () => {
    render(<Blacklist />);
    fireEvent.click(await screen.findByRole("button", { name: "Unblock" }));
    await screen.findByText(/Unblock Sam Rivera\?/i);

    fireEvent.click(
      screen.getByRole("button", { name: "Unblock", hidden: false }),
    );

    await waitFor(() => expect(api.unblockUser).toHaveBeenCalledWith(1));
    await waitFor(() =>
      expect(screen.queryByText("Sam Rivera")).not.toBeInTheDocument(),
    );
  });

  it("Cancel closes the dialog without unblocking", async () => {
    render(<Blacklist />);
    fireEvent.click(await screen.findByRole("button", { name: "Unblock" }));
    await screen.findByText(/Unblock Sam Rivera\?/i);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(
        screen.queryByText(/Unblock Sam Rivera\?/i),
      ).not.toBeInTheDocument(),
    );
    expect(api.unblockUser).not.toHaveBeenCalled();
  });

  it("keeps the row and shows an error toast when unblock fails", async () => {
    api.unblockUser.mockRejectedValue(new Error("network error"));

    render(<Blacklist />);
    fireEvent.click(await screen.findByRole("button", { name: "Unblock" }));
    await screen.findByText(/Unblock Sam Rivera\?/i);
    fireEvent.click(
      screen.getByRole("button", { name: "Unblock", hidden: false }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("network error"),
    );
    expect(screen.getByText("Sam Rivera")).toBeInTheDocument();
  });
});
