import { ArrowRight } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { renderBody } from "@/whatsNew/renderBody";

// Entry dates are calendar days, so they are read and shown in UTC to keep
// "2026-11-10" from turning into Nov 9 west of Greenwich.
const formatDate = (isoDay) =>
  new Date(`${isoDay}T00:00:00Z`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });

/**
 * Side panel listing What's new entries, newest first.
 *
 * @param {Object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {Array<{id: string, date?: string, title: string, body: string, isNew: boolean}>} props.entries
 *   Entries the viewer may see; `isNew` until they follow "Show me".
 * @param {(entry: Object) => void} props.onShowMe - Follows an entry's link.
 * @returns {JSX.Element}
 */
const WhatsNewPanel = ({ open, onOpenChange, entries, onShowMe }) => (
  <Sheet open={open} onOpenChange={onOpenChange}>
    {/* Above the fixed header (z-100), which would otherwise cover the top. */}
    <SheetContent className="z-[110] overflow-y-auto sm:max-w-md">
      <SheetHeader>
        <SheetTitle>What&apos;s new</SheetTitle>
        <SheetDescription>Recent changes to Purrf.</SheetDescription>
      </SheetHeader>
      <ul className="flex flex-col gap-3 px-4 pb-4">
        {entries.map((entry) => (
          <li
            key={entry.id}
            data-testid={`whats-new-entry-${entry.id}`}
            className="flex flex-col gap-1.5 rounded-lg border p-4"
          >
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {entry.date && (
                <time dateTime={entry.date}>{formatDate(entry.date)}</time>
              )}
              {entry.isNew && <Badge>New</Badge>}
            </div>
            <h3 className="text-sm font-semibold">{entry.title}</h3>
            <p className="text-sm text-muted-foreground">
              {renderBody(entry.body)}
            </p>
            <Button
              variant="link"
              className="h-auto self-start p-0"
              onClick={() => onShowMe(entry)}
              aria-label={`Show me: ${entry.title}`}
            >
              Show me
              <ArrowRight aria-hidden="true" />
            </Button>
          </li>
        ))}
      </ul>
    </SheetContent>
  </Sheet>
);

export default WhatsNewPanel;
