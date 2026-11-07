import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Asks which task to walk through after the basics tour, when the viewer
 * qualifies for more than one. Tasks already completed carry a check.
 *
 * @param {Object} props
 * @param {Array<{key: string, title: string, completed: boolean}>} props.tasks -
 *   The tasks to offer, in order.
 * @param {(key: string) => void} props.onChoose - A task was picked.
 * @param {() => void} props.onClose - The dialog was closed.
 * @param {() => void} props.onExplore - The viewer chose to explore alone,
 *   turning the offered tasks down.
 * @returns {JSX.Element}
 */
const TaskChooser = ({ tasks, onChoose, onClose, onExplore }) => (
  <Dialog
    open
    onOpenChange={(open) => {
      if (!open) onClose();
    }}
  >
    <DialogContent className="sm:max-w-sm">
      <DialogHeader>
        <DialogTitle>What would you like to do?</DialogTitle>
        <DialogDescription>
          Pick one to walk through it step by step.
        </DialogDescription>
      </DialogHeader>
      <div className="flex flex-col gap-2">
        {tasks.map((task) => (
          <Button
            key={task.key}
            type="button"
            variant="outline"
            className="justify-start"
            onClick={() => onChoose(task.key)}
          >
            {task.completed ? (
              <Check aria-hidden="true" className="text-primary" />
            ) : (
              <span aria-hidden="true" className="size-4" />
            )}
            {task.title}
            {task.completed && <span className="sr-only"> (completed)</span>}
          </Button>
        ))}
      </div>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onExplore}>
          I&apos;ll explore on my own
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

export default TaskChooser;
