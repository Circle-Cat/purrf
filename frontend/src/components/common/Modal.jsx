import React from "react";

/**
 * A reusable Modal component.
 *
 * This component displays a modal dialog over a backdrop. Clicking the backdrop
 * will trigger the `onClose` callback, while clicks inside the modal content
 * will not close it. Supports accessibility via `role` and `aria-modal`.
 *
 * @param {Object} props - Component props
 * @param {boolean} props.isOpen - Controls whether the Modal is visible
 * @param {Function} props.onClose - Callback triggered when the modal should close
 * @param {React.ReactNode} props.children - Content to render inside the modal
 *
 * @example
 * <Modal isOpen={isOpen} onClose={handleClose}>
 *   <p>This is the modal content</p>
 * </Modal>
 */
const Modal = ({ isOpen, onClose, children }) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] grid place-items-center bg-black/25"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex max-h-[85vh] w-[min(900px,92vw)] flex-col items-stretch justify-start overflow-hidden rounded-xl border bg-background shadow-[0_10px_35px_rgba(0,0,0,0.25)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  );
};

export default Modal;
