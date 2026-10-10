import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  NOTIFICATION_STATES,
  stageLabel,
} from "@/pages/MentorshipManagement/components/email/emailLabels";

/**
 * Pick a notification stage, then its state beside it. A state means nothing
 * without its stage, so the two are never offered where one can be set
 * without the other.
 *
 * @param {{
 *   stages: Array<{value: string, label: string}>,
 *   stage: string,
 *   state: string,
 *   onChange: (next: {stage: string, state: string}) => void,
 * }} props
 * @returns {JSX.Element}
 */
const NotificationFilter = ({ stages, stage, state, onChange }) => {
  const stateLabel = NOTIFICATION_STATES.find((s) => s.value === state)?.label;
  const label =
    stage && stateLabel
      ? `${stageLabel(stage)} · ${stateLabel}`
      : "Any notification";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          aria-label="Notification filter"
          className="h-8 text-xs font-normal"
        >
          {label}
          <ChevronDown className="ml-1 h-3 w-3" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuItem onSelect={() => onChange({ stage: "", state: "" })}>
          Any notification
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {stages.map((s) => (
          <DropdownMenuSub key={s.value}>
            <DropdownMenuSubTrigger>{s.label}</DropdownMenuSubTrigger>
            <DropdownMenuPortal>
              <DropdownMenuSubContent>
                {NOTIFICATION_STATES.map((st) => (
                  <DropdownMenuItem
                    key={st.value}
                    onSelect={() =>
                      onChange({ stage: s.value, state: st.value })
                    }
                  >
                    {st.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuSubContent>
            </DropdownMenuPortal>
          </DropdownMenuSub>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default NotificationFilter;
