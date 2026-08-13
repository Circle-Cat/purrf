import { useState } from "react";
import { Card } from "@/components/ui/card";
import TimeOffCard from "@/pages/LeavePrototype/TimeOffCard";
import RequestDialog from "@/pages/LeavePrototype/RequestDialog";
import HolidaysDialog from "@/pages/LeavePrototype/HolidaysDialog";
import RequestsPage from "@/pages/LeavePrototype/RequestsPage";
import LedgerPage from "@/pages/LeavePrototype/LedgerPage";
import {
  COMPANY_HOLIDAYS,
  CURRENT_USER,
} from "@/pages/LeavePrototype/mockData";
import {
  groupHolidays,
  ledgerBalance,
  pendingReserved,
  today,
} from "@/pages/LeavePrototype/leaveCalc";

/**
 * EmployeeView
 *
 * The employee side of the leave module, arranged the way it will actually
 * ship: a single card on the personal dashboard, plus the places its four
 * buttons lead.
 *
 * Requesting and the holiday calendar are dialogs, so the dashboard stays put
 * for the two things people do most often. The two histories are pages,
 * because they are scrolled and will eventually want filtering — this
 * prototype has no router, so they are swapped in with a back link, which is
 * the same shape the routed version will take.
 *
 * @param {object} props
 * @param {Array<object>} props.ledger - balance rows for the current user
 * @param {Array<object>} props.requests - the current user's requests
 * @param {(draft: object) => void} props.onSubmit
 * @param {(id: number) => void} props.onWithdraw
 * @param {(id: number) => void} props.onRequestCancel
 * @returns {JSX.Element}
 */
const EmployeeView = ({
  ledger,
  requests,
  onSubmit,
  onWithdraw,
  onRequestCancel,
}) => {
  const [page, setPage] = useState("dashboard");
  const [requesting, setRequesting] = useState(false);
  const [showingHolidays, setShowingHolidays] = useState(false);

  const balance = ledgerBalance(ledger);
  const pending = pendingReserved(requests);
  const available = Math.round((balance - pending) * 100) / 100;

  const used = ledger
    .filter((r) => r.entryType === "leave_deduction")
    .reduce((s, r) => s + Math.abs(r.hours), 0);

  const pendingCount = requests.filter((r) =>
    ["pending", "cancel_pending"].includes(r.status),
  ).length;

  /** Segments still ahead — a segment counts as upcoming until its last day. */
  const upcomingSegments = groupHolidays(COMPANY_HOLIDAYS).filter(
    (s) => s.end >= today(),
  );

  /**
   * The picker lists individual dates rather than whole segments. Whether a
   * break can be traded at all is decided for the break, but how much of one to
   * work is the employee's choice, so the dates are what they pick from.
   */
  const exchangeableDays = upcomingSegments
    .filter((segment) => segment.exchangeable)
    .flatMap((segment) =>
      segment.dates
        .filter((date) => date >= today())
        .map((date) => ({ date, segment })),
    );

  // Dialogs live outside the page switch so they stay mounted wherever you
  // opened them from.
  const dialogs = (
    <>
      <RequestDialog
        open={requesting}
        onOpenChange={setRequesting}
        requests={requests}
        available={available}
        exchangeableDays={exchangeableDays}
        approverName={CURRENT_USER.managerName}
        onSubmit={onSubmit}
      />
      <HolidaysDialog
        open={showingHolidays}
        onOpenChange={setShowingHolidays}
        segments={upcomingSegments}
      />
    </>
  );

  if (page === "requests") {
    return (
      <>
        {dialogs}
        <RequestsPage
          requests={requests}
          onBack={() => setPage("dashboard")}
          onWithdraw={onWithdraw}
          onRequestCancel={onRequestCancel}
        />
      </>
    );
  }

  if (page === "ledger") {
    return (
      <>
        {dialogs}
        <LedgerPage
          ledger={ledger}
          balance={balance}
          pending={pending}
          available={available}
          onBack={() => setPage("dashboard")}
        />
      </>
    );
  }

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      {dialogs}

      <header>
        <h1 className="text-xl font-semibold text-slate-900">
          Personal dashboard
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {CURRENT_USER.name} · {CURRENT_USER.level} · reports to{" "}
          {CURRENT_USER.managerName}
        </p>
      </header>

      <TimeOffCard
        available={available}
        pending={pending}
        used={used}
        pendingCount={pendingCount}
        onRequest={() => setRequesting(true)}
        onViewHolidays={() => setShowingHolidays(true)}
        onViewRequests={() => setPage("requests")}
        onViewLedger={() => setPage("ledger")}
      />

      {/* Standing in for the cards this one will sit among, so the card is
          judged at the size it will actually have on the page. */}
      <Card className="p-5 border-dashed">
        <p className="text-sm text-slate-400">
          The dashboard&apos;s other cards — mentorship, work activity, my
          applications — sit here. Time off is one card among them, which is why
          it stays three figures and four buttons.
        </p>
      </Card>
    </div>
  );
};

export default EmployeeView;
