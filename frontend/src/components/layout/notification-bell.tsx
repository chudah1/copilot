"use client";

import { useState, useRef, useEffect } from "react";
import useSWR, { mutate } from "swr";
import { api, fetcher } from "@/lib/api";
import type { UserNotification } from "@/types";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function notificationIcon(type: string) {
  if (type === "pre_earnings") return "○";
  if (type === "post_earnings") return "●";
  return "·";
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data: notifications = [] } = useSWR<UserNotification[]>(
    "/api/notifications",
    fetcher,
    { refreshInterval: 60000 }
  );

  const unread = notifications.filter((n) => !n.read);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function markRead(id: string) {
    await api(`/api/notifications/${id}/read`, { method: "POST" });
    mutate("/api/notifications");
  }

  async function markAllRead() {
    await Promise.all(unread.map((n) => api(`/api/notifications/${n.id}/read`, { method: "POST" })));
    mutate("/api/notifications");
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex items-center justify-center w-8 h-8 text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Notifications"
      >
        {/* Bell icon */}
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M8 1.5a4.5 4.5 0 0 0-4.5 4.5c0 2.5-.5 3.5-1 4h11c-.5-.5-1-1.5-1-4A4.5 4.5 0 0 0 8 1.5Z" />
          <path d="M6.5 13.5a1.5 1.5 0 0 0 3 0" />
        </svg>
        {unread.length > 0 && (
          <span className="absolute top-0.5 right-0.5 flex items-center justify-center w-4 h-4 rounded-full bg-primary text-[9px] font-mono text-primary-foreground leading-none">
            {unread.length > 9 ? "9+" : unread.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-sm border border-border bg-card shadow-lg z-50">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
            <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              Notifications
            </span>
            {unread.length > 0 && (
              <button
                onClick={markAllRead}
                className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground hover:text-foreground transition-colors"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-4 py-6 text-center font-mono text-[11px] text-muted-foreground">
                No notifications yet
              </p>
            ) : (
              notifications.slice(0, 20).map((n) => (
                <div
                  key={n.id}
                  onClick={() => !n.read && markRead(n.id)}
                  className={`flex gap-3 px-4 py-3 border-b border-border/50 last:border-0 cursor-pointer hover:bg-muted/30 transition-colors ${
                    !n.read ? "bg-primary/4" : ""
                  }`}
                >
                  <span className="font-mono text-[11px] text-muted-foreground mt-0.5 shrink-0">
                    {notificationIcon(n.notification_type)}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[12px] text-foreground leading-snug whitespace-pre-wrap">
                      {n.content}
                    </p>
                    <p className="font-mono text-[10px] text-muted-foreground mt-1">
                      {timeAgo(n.created_at)}
                    </p>
                  </div>
                  {!n.read && (
                    <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-primary" />
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
