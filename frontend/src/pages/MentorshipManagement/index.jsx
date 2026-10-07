import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import PendingApprovalsCard from "@/pages/MentorshipManagement/components/PendingApprovalsCard";
import { useMyMentorshipApprovals } from "@/pages/MentorshipManagement/hooks/useMyMentorshipApprovals";
import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";
import ParticipantSearchCard from "@/pages/MentorshipManagement/components/ParticipantSearchCard";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";

/**
 * MentorshipManagement
 *
 * Admin page for managing mentorship rounds and participant search. Entry is
 * gated on MENTORSHIP_ADMIN_READ or MENTORSHIP_ADMIN_WRITE (route + sidebar).
 * RoundsManagementCard renders for either permission (basic round list needs
 * no backend permission at all; write-only users get create/edit affordances
 * but no per-round detail stats). ParticipantSearchCard requires
 * MENTORSHIP_ADMIN_READ, as does the rounds table's Feedback column.
 * PendingApprovalsCard leads the page for a mentorship.approve holder with
 * requests waiting on them, behind the matching-run flag like the approvals
 * themselves.
 *
 * Route: /mentorship-management
 *
 * @returns {JSX.Element}
 */
const MentorshipManagement = () => {
  const { permissions } = useAuth();
  const canRead = permissions.includes(PERMISSIONS.MENTORSHIP_ADMIN_READ);
  const canWrite = permissions.includes(PERMISSIONS.MENTORSHIP_ADMIN_WRITE);
  const canApprove = permissions.includes(PERMISSIONS.MENTORSHIP_APPROVE);
  const flags = useFeatureFlags();
  const matchingOn = Boolean(flags[FEATURE_FLAGS.MATCHING_RUN]);
  const { requests } = useMyMentorshipApprovals(canApprove && matchingOn);

  const {
    sortedRounds,
    totals,
    isLoading,
    roundModalState,
    openCreate,
    openEdit,
    closeModal,
    saveRound,
  } = useMentorshipManagement(canRead);

  return (
    <div className="mentorship-management">
      {requests.length > 0 && <PendingApprovalsCard requests={requests} />}
      {(canRead || canWrite) && (
        <RoundsManagementCard
          rounds={sortedRounds}
          totals={totals}
          isLoading={isLoading}
          roundModalState={roundModalState}
          openCreate={openCreate}
          openEdit={openEdit}
          closeModal={closeModal}
          saveRound={saveRound}
          canWriteRounds={canWrite}
          canReadFeedback={canRead}
        />
      )}
      {canRead && <ParticipantSearchCard />}
    </div>
  );
};

export default MentorshipManagement;
