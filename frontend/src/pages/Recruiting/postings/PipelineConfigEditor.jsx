import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const STAGES = ["recruiter_screening", "behavioral", "tech", "board_review"];
const ASSIGNABLE = new Set(["recruiter_screening", "behavioral"]);
const NONE = "__none__";

/** A user-picker Select backed by an ApproverDto[] pool. */
const PeoplePicker = ({ label, pool, value, onChange }) => (
  <Select
    value={value != null ? String(value) : NONE}
    onValueChange={(v) => onChange(v === NONE ? undefined : Number(v))}
  >
    <SelectTrigger aria-label={label} className="max-w-xs">
      <SelectValue placeholder="— none —" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value={NONE}>— none —</SelectItem>
      {pool.map((u) => (
        <SelectItem key={u.userId} value={String(u.userId)}>
          {u.name} ({u.email})
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

/**
 * Editor for a posting's interview pipeline: owner + ordered selected stages
 * (each with rounds / referralSkippable, and a default assignee on
 * screening/behavioral).
 *
 * @param {{value: {ownerId?: number, stages: object[]},
 *          onChange: (next: object) => void,
 *          interviewPool: object[], jobOwners: object[]}} props
 */
const PipelineConfigEditor = ({
  value = { stages: [] },
  onChange,
  interviewPool = [],
  jobOwners = [],
}) => {
  const stages = value.stages ?? [];
  const stageOf = (name) => stages.find((s) => s.stage === name);

  /** Re-emit stages in canonical order after a mutation map. */
  const emitStages = (next) =>
    onChange({
      ...value,
      stages: STAGES.filter((n) => next[n]).map((n) => next[n]),
    });
  const asMap = () => Object.fromEntries(stages.map((s) => [s.stage, s]));

  const toggleStage = (name, on) => {
    const map = asMap();
    if (on) map[name] = { stage: name, rounds: 1, referralSkippable: false };
    else delete map[name];
    emitStages(map);
  };
  const patchStage = (name, fields) => {
    const map = asMap();
    if (!map[name]) return;
    map[name] = { ...map[name], ...fields };
    emitStages(map);
  };

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-slate-700">Interview pipeline</p>
      <div className="space-y-1">
        <Label>Owner</Label>
        <PeoplePicker
          label="Owner"
          pool={jobOwners}
          value={value.ownerId}
          onChange={(ownerId) => onChange({ ...value, ownerId })}
        />
      </div>
      {STAGES.map((name) => {
        const s = stageOf(name);
        return (
          <div
            key={name}
            className="space-y-2 rounded-md border border-slate-200 p-3"
          >
            <Label className="flex items-center gap-2">
              <Checkbox
                checked={!!s}
                onCheckedChange={(on) => toggleStage(name, !!on)}
                aria-label={name
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (c) => c.toUpperCase())}
              />
              {name}
            </Label>
            {s && (
              <div className="flex flex-wrap items-center gap-4 pl-6">
                <Label className="flex items-center gap-2 text-sm">
                  Rounds
                  <Input
                    type="number"
                    min={1}
                    aria-label={`${name} rounds`}
                    className="w-20"
                    value={s.rounds}
                    onChange={(e) =>
                      patchStage(name, {
                        rounds: Math.max(1, Number(e.target.value) || 1),
                      })
                    }
                  />
                </Label>
                <Label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={s.referralSkippable}
                    onCheckedChange={(v) =>
                      patchStage(name, { referralSkippable: !!v })
                    }
                    aria-label={`${name} referral skippable`}
                  />
                  Referral skippable
                </Label>
                {ASSIGNABLE.has(name) && (
                  <Label className="flex items-center gap-2 text-sm">
                    Default assignee
                    <PeoplePicker
                      label={`${name} assignee`}
                      pool={interviewPool}
                      value={s.defaultAssigneeId}
                      onChange={(id) =>
                        patchStage(name, { defaultAssigneeId: id })
                      }
                    />
                  </Label>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default PipelineConfigEditor;
