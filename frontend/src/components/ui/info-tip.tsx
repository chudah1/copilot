import { Info } from "lucide-react";

interface InfoTipProps {
  label: string;
  children: string;
  className?: string;
  align?: "start" | "center" | "end";
}

const TOOLTIP_POSITION = {
  start: "left-0",
  center: "left-1/2 -translate-x-1/2",
  end: "right-0",
} as const;

export function InfoTip({ label, children, className = "", align = "start" }: InfoTipProps) {
  return (
    <span className={`group/info relative inline-flex shrink-0 align-middle ${className}`}>
      <button
        type="button"
        aria-label={`${label}: ${children}`}
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full text-muted-foreground/70 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
      >
        <Info aria-hidden="true" className="h-3.5 w-3.5" strokeWidth={1.8} />
      </button>
      <span
        role="tooltip"
        className={`pointer-events-none invisible absolute top-[calc(100%+0.45rem)] z-50 w-64 max-w-[calc(100vw-2rem)] border border-border bg-card px-3 py-2 font-sans text-xs normal-case leading-relaxed tracking-normal text-foreground opacity-0 shadow-xl transition-opacity group-hover/info:visible group-hover/info:opacity-100 group-focus-within/info:visible group-focus-within/info:opacity-100 ${TOOLTIP_POSITION[align]}`}
      >
        {children}
      </span>
    </span>
  );
}
