"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface PositionNoteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  saving: boolean;
  onSave: (content: string) => Promise<void>;
}

export function PositionNoteDialog({
  open,
  onOpenChange,
  saving,
  onSave,
}: PositionNoteDialogProps) {
  const [note, setNote] = useState("");

  const handleSave = async () => {
    const content = note.trim();
    if (!content) return;
    await onSave(content);
    setNote("");
    onOpenChange(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!saving) onOpenChange(nextOpen);
      }}
    >
      <DialogContent className="product-panel product-panel-muted max-w-lg p-0 overflow-hidden">
        <DialogHeader className="px-5 pt-5 pr-14 sm:px-6 sm:pt-6 sm:pr-14">
          <DialogTitle className="font-display italic text-[1.65rem] leading-tight">
            Add a note to this position
          </DialogTitle>
          <DialogDescription className="mt-2">
            Record a change in your thinking, a question to revisit, or something you noticed.
            The note will appear in the position history.
          </DialogDescription>
        </DialogHeader>
        <div className="px-5 pb-5 sm:px-6">
          <textarea
            aria-label="Position note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="What do you want to remember?"
            rows={5}
            autoFocus
            className="w-full resize-none border border-border bg-background px-4 py-3 font-sans text-sm leading-relaxed text-foreground placeholder:text-muted-foreground/50 focus:border-primary/50 focus:outline-none"
          />
        </div>
        <DialogFooter className="mx-0 mb-0 rounded-none px-5 py-4 sm:px-6">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            onClick={() => void handleSave()}
            disabled={saving || note.trim().length === 0}
          >
            {saving ? "Saving…" : "Save note"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
