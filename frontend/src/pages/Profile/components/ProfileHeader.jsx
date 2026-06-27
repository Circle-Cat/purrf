import { formatTimezoneLabel } from "@/utils/dateTime";
import { Button } from "@/components/ui/button";

const ProfileHeader = ({ info, onEditClick }) => {
  return (
    <div className="grow">
      <h1 className="m-0 flex items-center justify-between text-4xl font-bold leading-tight tracking-tight text-foreground">
        <span>
          {info.firstName}
          {info.preferredName ? ` (${info.preferredName})` : ""}
          {` ${info.lastName}`}
          {info.timezone && (
            <span className="ml-3 whitespace-nowrap rounded-md bg-muted px-3 py-1 text-[0.35em] font-medium text-muted-foreground">
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
