import React from "react";

const ExperienceEditModal = ({ isOpen, onClose, initialData, onSave }) => {
  if (!isOpen) return null;

  return (
    <div className="modal placeholder">
      <div>
        <h2>Experience Edit Modal</h2>

        <p>This is a placeholder modal.</p>

        <pre>{JSON.stringify(initialData, null, 2)}</pre>

        <div style={{ marginTop: 16 }}>
          <button onClick={() => onSave(initialData)}>Save</button>

          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};

export default ExperienceEditModal;
