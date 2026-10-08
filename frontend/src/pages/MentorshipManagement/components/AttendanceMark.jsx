import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * A red "!" whose tooltip lists a live pair's flagged meetings, one per line.
 *
 * @param {{ lines: string[] }} props
 */
const AttendanceMark = ({ lines }) => (
  <TooltipProvider>
    <Tooltip>
      <TooltipTrigger
        type="button"
        aria-label={`Attendance issues: ${lines.join(", ")}`}
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-red-600 text-[10px] font-bold text-white"
      >
        !
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        {lines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
);

export default AttendanceMark;
