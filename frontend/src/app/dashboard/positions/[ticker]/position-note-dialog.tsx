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
      <DialogContent className="product-panel max-w-lg overflow-hidden border border-border/70 bg-background/96 p-0 shadow-[0_24px_80px_rgba(15,23,42,0.16)]">
        <DialogHeader className="px-5 pt-5 pr-14 sm:px-6 sm:pt-6 sm:pr-14">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Position note
          </p>
          <DialogTitle className="font-display italic text-[1.65rem] leading-tight">
            Capture a note for this position
          </DialogTitle>
          <DialogDescription className="mt-2">
            Save a change in your thinking, a question to revisit, or something you want future you to remember.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-5 border-t border-border/60 px-5 py-5 sm:px-6 lg:grid-cols-[minmax(0,1fr)_13rem]">
          <textarea
            aria-label="Position note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="What changed, what stood out, or what should you check later?"
            rows={5}
            autoFocus
            className="w-full resize-none border border-border bg-background px-4 py-3 font-sans text-sm leading-relaxed text-foreground placeholder:text-muted-foreground/50 focus:border-primary/50 focus:outline-none"
          />
          <aside className="space-y-3 border-t border-border/50 pt-4 lg:border-t-0 lg:pt-0">
            <div className="product-panel border border-border/60 bg-background/72 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Good note
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/78">
                Capture what you noticed, what it might mean, or what you want to check later.
              </p>
            </div>
            <div className="product-panel border border-border/60 bg-background/72 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Where it goes
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/75">
                The note appears in the decision trail so it stays tied to the broader reasoning around this position.
              </p>
            </div>
          </aside>
        </div>
        <DialogFooter className="mx-0 mb-0 rounded-none border-t border-border/60 px-5 py-4 sm:px-6">
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
            {saving ? "Saving…" : "Add note"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
