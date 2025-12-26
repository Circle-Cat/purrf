import "@/pages/Profile/components/ProfileHeader.css";
import { formatTimezoneLabel } from "@/pages/Profile/utils";
import { Button } from "@/components/ui/button";

const ProfileHeader = ({ info, onEditClick }) => {
  return (
    <div className="user-details">
      <h1 className="user-name">
        <span>
          {info.firstName}
          {info.preferredName ? ` (${info.preferredName})` : ""}
          {` ${info.lastName}`}
          {info.timezone && (
            <span className="user-timezone">
              {formatTimezoneLabel(info.timezone)}
            </span>
          )}
        </span>
        <Button size="sm" aria-label="Edit Profile" onClick={onEditClick}>
          Edit Profile
        </Button>
      </h1>
    </div>
  );
};

export default ProfileHeader;
