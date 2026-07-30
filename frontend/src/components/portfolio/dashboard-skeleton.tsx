"use client";

export function DashboardSkeleton() {
  return (
    <div className="min-h-[calc(100vh-84px)] flex flex-col animate-pulse bg-background">
      {/* Stat Strip Skeleton */}
      <div className="border-b border-border bg-card px-8 py-4">
        <div className="flex items-center justify-between gap-6 flex-wrap">
          <div className="flex items-baseline gap-4">
            <div>
              <div className="h-[9px] w-14 bg-muted rounded mb-2" />
              <div className="flex items-baseline gap-3">
                <div className="h-8 w-36 bg-muted rounded" />
                <div className="h-4 w-12 bg-muted rounded" />
              </div>
            </div>
            <div className="h-8 w-px bg-border hidden sm:block" />
            <div className="hidden sm:flex items-center gap-5">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex flex-col items-center">
                  <div className="h-4 w-6 bg-muted rounded" />
                  <div className="h-2 w-12 bg-muted rounded mt-2" />
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="h-[26px] w-16 bg-muted rounded" />
            <div className="h-[26px] w-20 bg-muted rounded" />
          </div>
        </div>
      </div>

      {/* Attention Section Skeleton */}
      <div className="px-8 pt-5">
        <div className="h-[9px] w-28 bg-muted rounded mb-3" />
        <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-56 h-[116px] shrink-0 border border-border bg-card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="h-3 w-12 bg-muted rounded" />
                <div className="h-3 w-8 bg-muted rounded" />
              </div>
              <div className="space-y-1.5">
                <div className="h-2 w-full bg-muted rounded" />
                <div className="h-2 w-5/6 bg-muted rounded" />
                <div className="h-2 w-2/3 bg-muted rounded" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Positions Grid Skeleton */}
      <div className="px-8 pt-6 pb-8 flex-1">
        <div className="flex items-center justify-between mb-4">
          <div className="h-[9px] w-24 bg-muted rounded" />
          <div className="h-[9px] w-32 bg-muted rounded hidden sm:block" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div key={i} className="h-[188px] border border-border bg-card p-4 flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div>
                  <div className="h-3 w-10 bg-muted rounded" />
                  <div className="h-2.5 w-20 bg-muted rounded mt-1.5" />
                </div>
                <div className="h-2 w-2 bg-muted rounded-full" />
              </div>
              <div className="space-y-1.5 mt-2">
                <div className="h-[21px] w-24 bg-muted rounded" />
                <div className="h-[14px] w-16 bg-muted rounded mt-1" />
              </div>
              <div className="space-y-1.5 mt-auto">
                <div className="flex justify-between">
                  <div className="h-[10px] w-20 bg-muted rounded" />
                  <div className="h-[12px] w-6 bg-muted rounded" />
                </div>
                <div className="h-px bg-border w-full" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
