"use client";

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";
import { Info } from "lucide-react";

interface InfoTipProps {
  label: string;
  children: string;
  className?: string;
  iconClassName?: string;
  tooltipClassName?: string;
  align?: "start" | "center" | "end";
}

const subscribeToNothing = () => () => undefined;
const getClientSnapshot = () => true;
const getServerSnapshot = () => false;

export function InfoTip({
  label,
  children,
  className = "",
  iconClassName = "",
  tooltipClassName = "",
  align = "start",
}: InfoTipProps) {
  const tooltipId = useId();
  const [open, setOpen] = useState(false);
  const mounted = useSyncExternalStore(
    subscribeToNothing,
    getClientSnapshot,
    getServerSnapshot,
  );
  const [position, setPosition] = useState<{
    left: number;
    top: number;
    width: number;
  } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);

  const placeTooltip = useCallback(() => {
    const button = buttonRef.current;
    if (!button) return;

    const gutter = 12;
    const gap = 6;
    const width = Math.min(256, window.innerWidth - gutter * 2);
    const buttonRect = button.getBoundingClientRect();
    const tooltipHeight = tooltipRef.current?.offsetHeight ?? 0;

    let left = buttonRect.left;
    if (align === "center") {
      left = buttonRect.left + buttonRect.width / 2 - width / 2;
    } else if (align === "end") {
      left = buttonRect.right - width;
    }
    left = Math.max(gutter, Math.min(left, window.innerWidth - width - gutter));

    let top = buttonRect.bottom + gap;
    if (
      tooltipHeight > 0 &&
      top + tooltipHeight > window.innerHeight - gutter &&
      buttonRect.top - tooltipHeight - gap >= gutter
    ) {
      top = buttonRect.top - tooltipHeight - gap;
    }

    setPosition({ left, top, width });
  }, [align]);

  useLayoutEffect(() => {
    if (!open || !mounted) return;
    placeTooltip();
  }, [mounted, open, placeTooltip]);

  useEffect(() => {
    if (!open) return;

    const reposition = () => placeTooltip();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);

    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open, placeTooltip]);

  return (
    <span className={`relative inline-flex shrink-0 align-middle ${className}`}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={`Explain ${label}`}
        aria-describedby={tooltipId}
        aria-expanded={open}
        onClick={() => setOpen(true)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setOpen(false);
            event.currentTarget.blur();
          }
        }}
        className={`inline-flex h-6 w-6 cursor-help items-center justify-center rounded-full text-muted-foreground/70 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 ${iconClassName}`}
      >
        <Info aria-hidden="true" className="h-3.5 w-3.5" strokeWidth={1.8} />
      </button>
      {mounted &&
        open &&
        createPortal(
          <span
            ref={tooltipRef}
            id={tooltipId}
            role="tooltip"
            style={
              position
                ? {
                    left: position.left,
                    top: position.top,
                    width: position.width,
                  }
                : undefined
            }
            className={`pointer-events-none fixed z-[100] border border-border bg-card px-3 py-2 font-sans text-xs normal-case leading-relaxed tracking-normal text-foreground shadow-xl ${position ? "visible opacity-100" : "invisible opacity-0"} ${tooltipClassName}`}
          >
            {children}
          </span>,
          document.body,
        )}
    </span>
  );
}
