import React from "react";
import { formatTimeDuration } from "@/pages/Profile/utils";
import { Button } from "@/components/ui/button";

const ExperienceSection = ({ list, onEditClick }) => {
  return (
    <div className="mb-12">
      <div className="mb-5 flex items-center justify-between">
        <h3 className="mb-5 mt-0 text-xl font-semibold tracking-[-0.015em] text-foreground">
          Experience
        </h3>
        <Button size="sm" aria-label="Edit Experience" onClick={onEditClick}>
          +
        </Button>
      </div>

      {list && list.length > 0 ? (
        <div className="flex flex-col gap-6">
          {list.map((exp) => (
            <div
              key={exp.id}
              className="rounded-xl border border-accent bg-muted p-4"
            >
              <h6 className="mb-1.5 text-lg font-semibold text-foreground">
                {exp.title}
              </h6>
              <p className="m-0 text-[0.9375rem] leading-[1.5] text-foreground">
                {exp.company}
              </p>
              <p className="mt-2 flex items-center gap-1 text-sm text-foreground">
                {formatTimeDuration(
                  exp.startMonth,
                  exp.startYear,
                  exp.endMonth,
                  exp.endYear,
                  exp.isCurrentlyWorking,
                )}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-3 text-base leading-relaxed text-foreground">
          No experience added.
        </p>
      )}
    </div>
  );
};

export default ExperienceSection;
