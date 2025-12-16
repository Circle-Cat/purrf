import "@/pages/Profile/components/ProfileHeader.css";

const ProfileHeader = ({ info, canEdit, nextEditableDate, onEditClick }) => {
  return (
    <div className="user-details">
      <h1 className="user-name">
        <span>
          {info.firstName}
          {info.preferredName ? ` (${info.preferredName})` : ""}
          {` ${info.lastName}`}
          {info.timezone && (
            <span className="user-timezone">{info.timezone}</span>
          )}
        </span>

        <div className="tooltip-container">
          <button
            className={`edit-name-button ${!canEdit ? "disabled" : ""}`}
            aria-label="Edit Profile"
            onClick={onEditClick}
            disabled={!canEdit}
            style={!canEdit ? { cursor: "not-allowed", opacity: 0.6 } : {}}
          >
            Edit Profile
          </button>
          <span className="tooltip-text">
            Personal Introduction can only be updated once every 30 days.
            <br />
            {!canEdit && `Next editable date: ${nextEditableDate}.`}
          </span>
        </div>
      </h1>
      <p className="user-title">
        {info.title || ""}
        {info.company && <span className="at-company"> at {info.company}</span>}
      </p>
    </div>
  );
};

export default ProfileHeader;
