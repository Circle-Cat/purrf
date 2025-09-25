import React from "react";
import "@/components/common/Modal.css";

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
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal"
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
