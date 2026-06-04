"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

interface InvalidateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  reason: string;
  onReasonChange: (value: string) => void;
  onConfirm: () => void;
}

export function InvalidateDialog({
  open,
  onOpenChange,
  investorProfile,
  reason,
  onReasonChange,
  onConfirm,
}: InvalidateDialogProps) {
  const placeholder =
    investorProfile === "thesis_driven"
      ? "Why is this thesis no longer valid?"
      : investorProfile === "hearsay_driven"
        ? "Why does the original story no longer hold?"
        : "Why is this reason no longer valid?";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="product-panel product-panel-muted max-w-lg p-0 overflow-hidden" showCloseButton={false}>
        <DialogHeader>
          <div className="px-5 pt-5 sm:px-6 sm:pt-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
              Thesis status
            </p>
            <DialogTitle className="font-display italic text-[1.65rem] leading-tight">Mark as broken</DialogTitle>
            <DialogDescription className="mt-2">
              Use this when the original case no longer holds and the position should stop being treated as intact.
            </DialogDescription>
          </div>
        </DialogHeader>
        <div className="px-5 pb-5 sm:px-6">
          <Textarea
            placeholder={placeholder}
            value={reason}
            onChange={(e) => onReasonChange(e.target.value)}
            className="min-h-28 border-border/70 bg-background/70"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Invalidate</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
