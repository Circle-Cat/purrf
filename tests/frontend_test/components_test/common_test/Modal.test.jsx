import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Modal from "@/components/common/Modal";

describe("Modal", () => {
  it("should not render the modal when isOpen is false", () => {
    render(
      <Modal isOpen={false} onClose={() => {}}>
        <div>Modal Content</div>
      </Modal>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("Modal Content")).not.toBeInTheDocument();
  });

  it("should render the modal when isOpen is true", () => {
    render(
      <Modal isOpen={true} onClose={() => {}}>
        <div>Modal Content</div>
      </Modal>,
    );

    expect(screen.getByRole("presentation")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Modal Content")).toBeInTheDocument();
  });

  it("should render children content inside the modal", () => {
    const testContent = "Hello, I am modal content!";
    render(
      <Modal isOpen={true} onClose={() => {}}>
        <p>{testContent}</p>
      </Modal>,
    );
    const modalDialog = screen.getByRole("dialog");
    expect(modalDialog).toBeInTheDocument();
    expect(screen.getByText(testContent)).toBeInTheDocument();
    expect(modalDialog).toContainElement(screen.getByText(testContent));
  });

  it("should call onClose when the backdrop is clicked", () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose}>
        <div>Modal Content</div>
      </Modal>,
    );

    const backdrop = screen.getByRole("presentation");
    fireEvent.click(backdrop);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("should NOT call onClose when the modal content is clicked", () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose}>
        <button>Click me!</button>
      </Modal>,
    );

    const modalContent = screen.getByRole("dialog");
    fireEvent.click(modalContent);

    expect(handleClose).not.toHaveBeenCalled();
  });

  it("should have correct accessibility attributes", () => {
    render(
      <Modal isOpen={true} onClose={() => {}}>
        <div>Test</div>
      </Modal>,
    );

    const backdrop = screen.getByRole("presentation");
    const modalDialog = screen.getByRole("dialog");

    expect(backdrop).toHaveAttribute("role", "presentation");
    expect(modalDialog).toHaveAttribute("role", "dialog");
    expect(modalDialog).toHaveAttribute("aria-modal", "true");
  });
});
