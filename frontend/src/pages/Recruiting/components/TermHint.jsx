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
        <TooltipContent className="max-w-xs">{term.hint}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default TermHint;
