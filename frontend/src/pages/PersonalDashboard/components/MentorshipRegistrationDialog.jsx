import React, { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/**
 * MentorshipRegistrationDialog
 *
 * NOTE:
 * This component currently serves as a **placeholder dialog**.
 * ...
 */
export default function MentorshipRegistrationDialog({
  currentRegistration,
  allPastPartners = [],
  isPartnersLoading,
  loadPastPartners,
  refreshRegistration,
  isLocked,
  onSave,
}) {
  const [isOpen, setIsOpen] = useState(false);

  const buttonText = isPartnersLoading
    ? "Loading..."
    : isLocked
      ? "View Registration"
      : "Register Next Round";

  const handleOpenChange = (open) => {
    setIsOpen(open);
    if (open) {
      refreshRegistration();
      loadPastPartners();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="default" disabled={isPartnersLoading}>
          {buttonText}
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {isLocked ? "Your Registration Details" : "Mentorship Registration"}
          </DialogTitle>
        </DialogHeader>

        <div className="py-4 space-y-6">
          <div className="text-sm text-muted-foreground">
            {isLocked
              ? "Registration is currently locked. You are viewing your submitted details."
              : "Fill out the form below to register for the next mentorship round."}
          </div>

          <div className="space-y-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium">Learning Goal</label>
              {isLocked ? (
                <div className="p-3 bg-muted rounded-md border text-sm italic">
                  {currentRegistration?.roundPreferences?.goal ||
                    "No goal specified"}
                </div>
              ) : (
                <textarea
                  className="w-full p-2 border rounded-md text-sm"
                  placeholder="What is your goal for this round?"
                  rows={3}
                  defaultValue={
                    currentRegistration?.roundPreferences?.goal || ""
                  }
                />
              )}
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium">
                {isLocked
                  ? "Historical Connections"
                  : "Your Past Partners (Reference)"}
              </label>
              <div className="p-3 bg-gray-50/50 rounded-md border border-dashed">
                {allPastPartners.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {allPastPartners.map((partner) => (
                      <span
                        key={partner.id}
                        className="inline-flex items-center px-2 py-1 rounded-secondary bg-purple-50 text-purple-700 text-xs border border-purple-100"
                      >
                        {partner.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">
                    {isPartnersLoading
                      ? "Loading history..."
                      : "No past partners found."}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <DialogTrigger asChild>
            <Button variant="outline">Close</Button>
          </DialogTrigger>

          {!isLocked && (
            <Button onClick={() => onSave()}>Submit Registration</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
