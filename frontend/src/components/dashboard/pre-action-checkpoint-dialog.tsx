"use client";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface PreActionCheckpointDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  hasExistingCase: boolean;
  ticker: string;
  whyOwnIt: string;
  mustRemainTrue: string;
  changeMind: string;
  onWhyOwnItChange: (value: string) => void;
  onMustRemainTrueChange: (value: string) => void;
  onChangeMindChange: (value: string) => void;
  onConfirm: () => void;
  saving: boolean;
}

export function PreActionCheckpointDialog({
  open,
  onOpenChange,
  investorProfile,
  hasExistingCase,
  ticker,
  whyOwnIt,
  mustRemainTrue,
  changeMind,
  onWhyOwnItChange,
  onMustRemainTrueChange,
  onChangeMindChange,
  onConfirm,
  saving,
}: PreActionCheckpointDialogProps) {
  const reasonNoun = investorProfile === "hearsay_driven" ? "reason" : "thesis";
  const title = hasExistingCase
    ? `Record why you are adding to ${ticker}`
    : `Write the ${reasonNoun} before ${ticker} becomes a real position`;
  const description = hasExistingCase
    ? "This note is saved to the decision trail so you can trace why this add made sense at the time."
    : `These answers carry into the ${reasonNoun} editor so this add starts with a real starting point instead of a blank page.`;
  const confirmLabel = hasExistingCase ? "Save note and add" : `Add and write ${reasonNoun}`;
  const disabled = saving || whyOwnIt.trim().length < 12 || changeMind.trim().length < 12;
  const whyThisMatters = investorProfile === "hearsay_driven"
    ? "This is the moment where a market idea turns into real capital. Write the part that made you add, not just the part that sounds persuasive."
    : investorProfile === "thesis_driven"
      ? "This is where a thesis becomes a capital allocation decision. You should be able to tell later whether this add was disciplined sizing or quiet drift."
      : "This pause matters most right before you add risk. It turns the action into a decision you can review later.";
  const minimum = investorProfile === "hearsay_driven"
    ? "One clear reason for the add and one clear sign that the original reason no longer holds."
    : investorProfile === "thesis_driven"
      ? "One specific reason for the add and one explicit condition that would make this sizing decision look wrong."
      : "One clear reason for the add and one clear condition that would make it look wrong.";

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !saving && onOpenChange(nextOpen)}>
      <DialogContent className="product-panel max-w-2xl overflow-hidden border border-border/70 bg-background/96 p-0 shadow-[0_24px_80px_rgba(15,23,42,0.16)]">
        <DialogHeader className="px-5 pt-5 pr-14 sm:px-6 sm:pt-6 sm:pr-14">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
            Pre-action checkpoint
          </p>
          <DialogTitle className="mt-2 font-display italic text-[1.85rem] leading-tight">
            {title}
          </DialogTitle>
          <DialogDescription className="mt-2 max-w-xl">
            {description}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 border-t border-border/60 px-5 py-5 sm:px-6 lg:grid-cols-[minmax(0,1fr)_15rem]">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Why does this deserve capital today?</Label>
              <Textarea
                value={whyOwnIt}
                onChange={(event) => onWhyOwnItChange(event.target.value)}
                rows={4}
                placeholder="Name the specific reason you are increasing the position now."
                className="min-h-28 bg-background/85"
              />
            </div>

            <div className="space-y-2">
              <Label>What must remain true after this add?</Label>
              <Textarea
                value={mustRemainTrue}
                onChange={(event) => onMustRemainTrueChange(event.target.value)}
                rows={4}
                placeholder="What business condition are you relying on to keep holding after adding?"
                className="min-h-24 bg-background/85"
              />
            </div>

            <div className="space-y-2">
              <Label>What would make this add feel wrong?</Label>
              <Textarea
                value={changeMind}
                onChange={(event) => onChangeMindChange(event.target.value)}
                rows={4}
                placeholder="Name the evidence that would make you regret increasing the position."
                className="min-h-24 bg-background/85"
              />
            </div>
          </div>

          <aside className="space-y-3 border-t border-border/50 pt-4 lg:border-t-0 lg:pt-0">
            <div className="product-panel border border-border/60 bg-background/72 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Why this matters
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                {whyThisMatters}
              </p>
            </div>
            <div className="product-panel border border-border/60 bg-background/72 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Minimum
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/75">
                {minimum}
              </p>
            </div>
          </aside>
        </div>

        <DialogFooter className="mx-0 mb-0 rounded-none border-t border-border/60 px-5 py-4 sm:px-6">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={disabled}>
            {saving ? "Saving…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
