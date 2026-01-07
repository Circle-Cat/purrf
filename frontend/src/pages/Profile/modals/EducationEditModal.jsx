import React from "react";
import { Button } from "@/components/ui/button";

const EducationEditModal = ({ isOpen, onClose, initialData, onSave }) => {
  if (!isOpen) return null;

  return (
    <div className="modal placeholder">
      <div>
        <h2>Education Edit Modal</h2>

        <p>This is a placeholder modal.</p>

        <pre>{JSON.stringify(initialData, null, 2)}</pre>

        <div style={{ marginTop: 16 }}>
          <Button onClick={() => onSave(initialData)}>Save</Button>

          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
};

export default EducationEditModal;
