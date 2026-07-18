import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";
import ParticipantSearchCard from "@/pages/MentorshipManagement/components/ParticipantSearchCard";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";

/**
 * MentorshipManagement
 *
 * Admin page for managing mentorship rounds and participant search. Entry is
 * gated on MENTORSHIP_ADMIN_READ or MENTORSHIP_ADMIN_WRITE (route + sidebar);
 * cards inside check read/write as appropriate.
 *
 * Route: /mentorship-management
 *
 * @returns {JSX.Element}
 */
const MentorshipManagement = () => {
  const { permissions } = useAuth();
  const canRead = permissions.includes(PERMISSIONS.MENTORSHIP_ADMIN_READ);
  const canWrite = permissions.includes(PERMISSIONS.MENTORSHIP_ADMIN_WRITE);

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
      {canRead && (
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
        />
      )}
      {canRead && <ParticipantSearchCard />}
    </div>
  );
};

export default MentorshipManagement;
