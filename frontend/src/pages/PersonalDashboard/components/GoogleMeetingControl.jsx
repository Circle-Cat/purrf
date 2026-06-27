import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import MeetingManagementDialog from "@/components/common/MeetingManagementDialog";

export const GoogleMeetingControl = ({ meetingRoundId, onRefresh }) => {
  const { [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: createGoogleMeeting } =
    useFeatureFlags();

  if (!createGoogleMeeting) return null;

  return (
    <MeetingManagementDialog roundId={meetingRoundId} onBooked={onRefresh} />
  );
};
