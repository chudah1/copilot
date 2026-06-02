"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
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
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display italic">Mark as broken</DialogTitle>
        </DialogHeader>
        <Textarea placeholder={placeholder} value={reason} onChange={(e) => onReasonChange(e.target.value)} />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Invalidate</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
