import { Ban, CheckCircle2, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fullName } from "@/pages/UserAdminPrototype/accountState";

const OUTCOME = {
  pending: {
    icon: Clock,
    label: "Block requested",
    className: "border-amber-300 bg-amber-50 text-amber-900",
  },
  approved: {
    icon: Ban,
    label: "Blocked",
    className: "border-rose-300 bg-rose-50 text-rose-800",
  },
  rejected: {
    icon: CheckCircle2,
    label: "Request rejected",
    className: "border-slate-300 bg-slate-100 text-slate-700",
  },
};

/**
 * DomainView
 *
 * A stand-in for a business page — the screening board, or mentorship
 * management. Both are represented by the same component because the point
 * being demonstrated is identical on each: raising a block request is not a
 * separate permission, it rides on already being authorized to be on this
 * page looking at this person.
 *
 * The evidence stays here too. A mentorship admin decides on no-show counts,
 * which are on their own table; sending them to another page to act would
 * separate the judgement from the act.
 *
 * @param {{title: string, subtitle: string, columns: object[], rows: object[],
 *   userById: Function, requestFor: Function, onRequest: Function}} props
 * @returns {JSX.Element}
 */
const DomainView = ({
  title,
  subtitle,
  columns,
  rows,
  userById,
  requestFor,
  onRequest,
}) => (
  <div className="space-y-4">
    <div>
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-0.5 text-sm text-slate-600">{subtitle}</p>
    </div>

    <div className="overflow-x-auto rounded-md border border-slate-200">
      <Table>
        <TableHeader>
          <TableRow className="bg-slate-50">
            <TableHead>Person</TableHead>
            {columns.map((column) => (
              <TableHead key={column.key}>{column.label}</TableHead>
            ))}
            <TableHead className="w-52">Block</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const user = userById(row.userId);
            const request = requestFor(row.userId);
            const outcome = request ? OUTCOME[request.status] : null;
            const Icon = outcome?.icon;
            return (
              <TableRow key={row.userId}>
                <TableCell className="font-medium text-slate-900">
                  {fullName(user)}
                </TableCell>
                {columns.map((column) => (
                  <TableCell key={column.key} className="text-slate-600">
                    {row[column.key]}
                  </TableCell>
                ))}
                <TableCell>
                  {user.isBlocked || outcome ? (
                    <div className="space-y-1">
                      <Badge
                        variant="outline"
                        className={
                          outcome
                            ? outcome.className
                            : OUTCOME.approved.className
                        }
                      >
                        {Icon && <Icon size={12} />}
                        {user.isBlocked
                          ? OUTCOME.approved.label
                          : outcome.label}
                      </Badge>
                      {request?.status === "rejected" &&
                        request.decisionNote && (
                          <p className="text-xs text-slate-500">
                            {request.decidedBy}: {request.decisionNote}
                          </p>
                        )}
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onRequest(user)}
                    >
                      Request block
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>

    <p className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
      Raising a request blocks nobody. It goes to whoever holds{" "}
      <code className="rounded bg-slate-200 px-1 text-xs">user.admin</code>, and
      the person carries on unaffected until that decision is made. Switch to
      the Operations view above to act on it.
    </p>
  </div>
);

export default DomainView;
