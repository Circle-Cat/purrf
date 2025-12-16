import React from "react";

const PersonalEditModal = ({
  isOpen,
  onClose,
  initialData,
  onSave,
  canEdit,
  nextEditableDate,
}) => {
  if (!isOpen) return null;

  return (
    <div className="modal placeholder">
      <h2>PersonalEditModal</h2>

      <pre style={{ fontSize: 12 }}>
        {JSON.stringify({ initialData, canEdit, nextEditableDate }, null, 2)}
      </pre>

      <div style={{ marginTop: 16 }}>
        <button onClick={() => onSave(initialData)}>Save</button>

        <button onClick={onClose}>Close</button>
      </div>
    </div>
  );
};

export default PersonalEditModal;
