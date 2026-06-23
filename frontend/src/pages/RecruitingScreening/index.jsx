import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { getBoard, viewApplication, advanceApplication } from "@/api/recruitingApi";
import ApplicationCard from "@/pages/RecruitingScreening/components/ApplicationCard";

/**
 * RecruitingScreening
 *
 * Kanban-style screening board for a single job posting. Displays active
 * (screening-stage) applications in three labeled columns: Screening, Hired,
 * and Rejected.
 *
 * NOTE (limitation): The backend `getBoard` endpoint returns only active
 * (screening) applications; it does not return previously hired/rejected cards.
 * The Hired and Rejected columns therefore only populate with cards that are
 * advanced *during this session*. A full historical view would require a
 * separate endpoint.
 *
 * Route: /recruiting/screening/:jobId
 *
 * Permission gates:
 *   - Page view: RECRUITING_APPLICATION_READ
 *   - Open button: RECRUITING_APPLICATION_READ
 *   - Hire/Reject buttons: RECRUITING_APPLICATION_ADVANCE
 *
 * @returns {JSX.Element}
 */
const RecruitingScreening = () => {
  const { jobId } = useParams();
  const { permissions } = useAuth();

  const canRead = permissions.includes(PERMISSIONS.RECRUITING_APPLICATION_READ);
  const canAdvance = permissions.includes(
    PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
  );

  /** @type {[Object[], Function]} Applications in the Screening column. */
  const [screeningCards, setScreeningCards] = useState([]);
  /** @type {[Object[], Function]} Applications moved to Hired during this session. */
  const [hiredCards, setHiredCards] = useState([]);
  /** @type {[Object[], Function]} Applications moved to Rejected during this session. */
  const [rejectedCards, setRejectedCards] = useState([]);
  /** @type {[boolean, Function]} Whether the board is loading. */
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!canRead) return;

    setIsLoading(true);
    getBoard(jobId)
      .then((res) => {
        setScreeningCards(res.data);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [jobId, canRead]);

  /**
   * Record the first screener view of an application and flip its isViewed
   * flag in local state.
   *
   * @param {number} id - The application ID.
   */
  const handleOpen = async (id) => {
    await viewApplication(id);
    setScreeningCards((prev) =>
      prev.map((c) => (c.id === id ? { ...c, isViewed: true } : c)),
    );
  };

  /**
   * Advance an application to the Hired stage and move it out of Screening.
   *
   * @param {number} id - The application ID.
   */
  const handleHire = async (id) => {
    await advanceApplication(id, "hired");
    setScreeningCards((prev) => {
      const card = prev.find((c) => c.id === id);
      if (card) setHiredCards((h) => [...h, { ...card, stage: "hired" }]);
      return prev.filter((c) => c.id !== id);
    });
  };

  /**
   * Advance an application to the Rejected stage and move it out of Screening.
   *
   * @param {number} id - The application ID.
   */
  const handleReject = async (id) => {
    await advanceApplication(id, "rejected");
    setScreeningCards((prev) => {
      const card = prev.find((c) => c.id === id);
      if (card) setRejectedCards((r) => [...r, { ...card, stage: "rejected" }]);
      return prev.filter((c) => c.id !== id);
    });
  };

  if (!canRead) {
    return (
      <div className="recruiting-screening p-6 text-center text-muted-foreground">
        You do not have permission to view applications.
      </div>
    );
  }

  return (
    <div className="recruiting-screening p-6">
      <h1 className="text-xl font-semibold mb-6">Screening Board</h1>

      {isLoading ? (
        <div className="py-10 text-center text-gray-500">
          Loading applications…
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {/* Screening column */}
          <ScreeningColumn title="Screening">
            {screeningCards.map((card) => (
              <ApplicationCard
                key={card.id}
                card={card}
                canRead={canRead}
                canAdvance={canAdvance}
                onOpen={handleOpen}
                onHire={handleHire}
                onReject={handleReject}
              />
            ))}
          </ScreeningColumn>

          {/* Hired column — populated only by cards advanced this session */}
          <ScreeningColumn title="Hired">
            {hiredCards.map((card) => (
              <ApplicationCard
                key={card.id}
                card={card}
                canRead={false}
                canAdvance={false}
                onOpen={() => {}}
                onHire={() => {}}
                onReject={() => {}}
              />
            ))}
          </ScreeningColumn>

          {/* Rejected column — populated only by cards advanced this session */}
          <ScreeningColumn title="Rejected">
            {rejectedCards.map((card) => (
              <ApplicationCard
                key={card.id}
                card={card}
                canRead={false}
                canAdvance={false}
                onOpen={() => {}}
                onHire={() => {}}
                onReject={() => {}}
              />
            ))}
          </ScreeningColumn>
        </div>
      )}
    </div>
  );
};

/**
 * A labeled column wrapper for the board grid.
 *
 * @param {Object}    props
 * @param {string}    props.title    - Column heading.
 * @param {React.ReactNode} props.children - ApplicationCard elements.
 * @returns {JSX.Element}
 */
function ScreeningColumn({ title, children }) {
  return (
    <Card className="border-gray-200 shadow-sm h-fit">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {children}
      </CardContent>
    </Card>
  );
}

export default RecruitingScreening;
