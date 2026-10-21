import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Says why a control is disabled, on hover and on keyboard focus.
 *
 * The reason hangs on a focusable wrapper, not on the control: a disabled
 * control takes no focus, and a browser sends it no mouse events, so nothing
 * attached to it is ever shown. The wrapper also lets the pointer through a
 * disabled child, which a disabled button does by its own class but a select
 * does not. A native `title` on the wrapper was tried first and showed only
 * sometimes, after a delay the browser decides; this is the same Tooltip the
 * rest of the app uses.
 *
 * @param {object} props
 * @param {string|null|undefined} props.reason Why the control is disabled, or
 *   nothing when it is not; the control is then rendered as is.
 * @param {import("react").ReactNode} props.children The control.
 * @returns {JSX.Element}
 */
const DisabledReason = ({ reason, children }) => {
  if (!reason) return <>{children}</>;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            className="inline-flex cursor-not-allowed [&>:disabled]:pointer-events-none"
          >
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{reason}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default DisabledReason;
