import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { GLOSSARY } from "@/pages/Recruiting/components/glossary";

/**
 * A term with its explanation attached, revealed on hover and on keyboard
 * focus. The dotted underline is what makes the explanation discoverable — a
 * hint nobody knows is there is not guidance.
 *
 * An id the glossary does not hold degrades to plain text with no trigger, so
 * a stage added on the backend can never break a page that renders it.
 *
 * @param {object} props
 * @param {string} props.id A glossary id, e.g. "stage.recruiter_screening".
 * @param {import("react").ReactNode} [props.children] Text to show in place of
 *          the glossary label.
 * @returns {JSX.Element|null}
 */
const TermHint = ({ id, children }) => {
  const term = GLOSSARY[id];

  if (!term) return children ? <>{children}</> : null;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger className="cursor-help underline decoration-dotted underline-offset-4">
          {children ?? term.label}
        </TooltipTrigger>
        {/* The shadcn primitive ships z-50, which loses to this app's fixed
            chrome -- the header sits at z-[100] and the sidebar at z-[90], so
            a hint opening upward from a badge near the page title renders
            behind the header. Clearing 100 is enough; dialogs live at z-[999]
            and up and should still cover a hint. */}
        <TooltipContent className="z-[110] max-w-xs">
          {term.hint}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default TermHint;
