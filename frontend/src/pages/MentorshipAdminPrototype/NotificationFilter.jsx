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
import { EMAIL_STATES } from "@/pages/MentorshipAdminPrototype/emailStatus";

/**
 * NotificationFilter
 *
 * One control, two levels: pick a notification, and its states open beside
 * it. A state means nothing without the notification it belongs to, so the
 * two are never offered side by side where one can be set without the other.
 *
 * @param {{steps: object[], step: string, state: string, onChange: (patch: {email: string, emailState: string}) => void}} props
 * @returns {JSX.Element}
 */
const NotificationFilter = ({ steps, step, state, onChange }) => {
  const chosen = steps.find((s) => s.key === step);
  const chosenState = EMAIL_STATES.find((s) => s.key === state);
  const label =
    chosen && chosenState
      ? `${chosen.label} · ${chosenState.label}`
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
        <DropdownMenuItem
          onSelect={() => onChange({ email: "", emailState: "" })}
        >
          Any notification
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {steps.map((s) => (
          <DropdownMenuSub key={s.key}>
            <DropdownMenuSubTrigger>{s.label}</DropdownMenuSubTrigger>
            <DropdownMenuPortal>
              <DropdownMenuSubContent>
                {EMAIL_STATES.map((st) => (
                  <DropdownMenuItem
                    key={st.key}
                    onSelect={() =>
                      onChange({ email: s.key, emailState: st.key })
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
