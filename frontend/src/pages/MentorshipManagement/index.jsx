import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";

/**
 * MentorshipManagement
 *
 * Admin page for managing mentorship rounds.
 * Route: /mentorship-management (MENTORSHIP_ADMIN role only)
 *
 * @returns {JSX.Element}
 */
const MentorshipManagement = () => {
  const {
    sortedRounds,
    totals,
    isLoading,
    roundModalState,
    openCreate,
    openEdit,
    closeModal,
    saveRound,
  } = useMentorshipManagement();

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
      />
    </div>
  );
};

export default MentorshipManagement;
