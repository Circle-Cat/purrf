import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";
import ParticipantSearchCard from "@/pages/MentorshipManagement/components/ParticipantSearchCard";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";

/**
 * MentorshipManagement
 *
 * Admin page for managing mentorship rounds and participant search. Entry is
 * gated on MENTORSHIP_MANAGEMENT_READ (route + sidebar); each section inside
 * has its own finer-grained permission check.
 *
 * Route: /mentorship-management
 *
 * @returns {JSX.Element}
 */
const MentorshipManagement = () => {
  const { permissions } = useAuth();
  const canReadRounds = permissions.includes(PERMISSIONS.MENTORSHIP_ROUND_READ);
  const canWriteRounds = permissions.includes(
    PERMISSIONS.MENTORSHIP_ROUND_WRITE,
  );
  const canReadParticipants = permissions.includes(
    PERMISSIONS.MENTORSHIP_PARTICIPANT_READ,
  );

  const {
    sortedRounds,
    totals,
    isLoading,
    roundModalState,
    openCreate,
    openEdit,
    closeModal,
    saveRound,
  } = useMentorshipManagement(canReadRounds);

  return (
    <div className="mentorship-management">
      {canReadRounds && (
        <RoundsManagementCard
          rounds={sortedRounds}
          totals={totals}
          isLoading={isLoading}
          roundModalState={roundModalState}
          openCreate={openCreate}
          openEdit={openEdit}
          closeModal={closeModal}
          saveRound={saveRound}
          canWriteRounds={canWriteRounds}
        />
      )}
      {canReadRounds && canReadParticipants && (
        <ParticipantSearchCard rounds={sortedRounds} />
      )}
    </div>
  );
};

export default MentorshipManagement;
