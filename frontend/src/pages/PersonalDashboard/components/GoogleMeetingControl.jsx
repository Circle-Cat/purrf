import { Button } from "@/components/ui/button";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

export const GoogleMeetingControl = ({ meetingRoundId }) => {
  const { [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: createGoogleMeeting } =
    useFeatureFlags();

  if (!createGoogleMeeting) return null;

  const handleManageMeetingsClick = () => {
    console.log("Current meetingRoundId:", meetingRoundId);
  };

  const isDisabled = meetingRoundId === null;

  return (
    <div title={isDisabled ? "No active mentorship round" : undefined}>
      <Button
        variant="default"
        onClick={handleManageMeetingsClick}
        disabled={isDisabled}
      >
        Manage Meetings
      </Button>
    </div>
  );
};
