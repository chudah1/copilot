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
        ? "Why does the original reason no longer hold?"
        : "Why is this reason no longer valid?";
  const noun = investorProfile === "hearsay_driven" ? "reason" : investorProfile === "thesis_driven" ? "thesis" : "reason";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="product-panel max-w-lg overflow-hidden border border-border/70 bg-background/96 p-0 shadow-[0_24px_80px_rgba(15,23,42,0.16)]"
        showCloseButton={false}
      >
        <DialogHeader className="px-5 pt-5 pr-14 sm:px-6 sm:pt-6 sm:pr-14">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Status change
          </p>
          <DialogTitle className="font-display italic text-[1.65rem] leading-tight">Mark this {noun} as no longer holding</DialogTitle>
          <DialogDescription className="mt-2">
            Use this when the original {noun} no longer holds and the position should stop being treated as intact.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-5 border-t border-border/60 px-5 py-5 sm:px-6 lg:grid-cols-[minmax(0,1fr)_13rem]">
          <Textarea
            placeholder={placeholder}
            value={reason}
            onChange={(e) => onReasonChange(e.target.value)}
            className="min-h-28 border-border/70 bg-background/70"
          />
          <aside className="space-y-3 border-t border-border/50 pt-4 lg:border-t-0 lg:pt-0">
            <div className="product-panel border border-border/60 bg-background/72 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Use this when
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/78">
                The core {noun} no longer holds, not when you just want to lower confidence or rewrite details.
              </p>
            </div>
            <div className="product-panel border border-border/60 bg-background/72 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Better alternative
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/75">
                If it still broadly holds, lower confidence or rewrite it instead of marking it as no longer holding.
              </p>
            </div>
          </aside>
        </div>
        <DialogFooter className="border-t border-border/60 px-5 py-4 sm:px-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Mark as no longer holding</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
