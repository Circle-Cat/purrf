import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";

/**
 * MentorshipManagement
 *
 * Admin page for managing mentorship rounds. Entry is gated on
 * MENTORSHIP_MANAGEMENT_READ (route + sidebar); what is shown inside depends on
 * the finer mentorship permissions: MENTORSHIP_ROUND_READ to view rounds and
 * MENTORSHIP_ROUND_WRITE to create or edit them.
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
      <RoundsManagementCard
        rounds={sortedRounds}
        totals={totals}
        isLoading={isLoading}
        roundModalState={roundModalState}
        openCreate={openCreate}
        openEdit={openEdit}
        closeModal={closeModal}
        saveRound={saveRound}
        canReadRounds={canReadRounds}
        canWriteRounds={canWriteRounds}
      />
    </div>
  );
};

export default MentorshipManagement;
