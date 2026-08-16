"use client";

export function DashboardSkeleton() {
  return (
    <div className="min-h-[calc(100vh-84px)] flex flex-col animate-pulse bg-background">
      <div className="px-4 pt-4 sm:px-8">
        <div className="product-panel overflow-hidden border border-border/70 bg-background/82 p-5 sm:p-6">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
            <div className="space-y-4">
              <div className="h-[10px] w-28 rounded bg-muted" />
              <div className="space-y-2">
                <div className="h-10 w-72 rounded bg-muted" />
                <div className="h-4 w-64 rounded bg-muted" />
              </div>
              <div className="product-panel h-[220px] border border-border/60 bg-background/70 p-6">
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-20 rounded bg-muted" />
                    <div className="h-3 w-28 rounded bg-muted" />
                  </div>
                  <div className="h-10 w-56 rounded bg-muted" />
                  <div className="space-y-2">
                    <div className="h-3 w-full rounded bg-muted" />
                    <div className="h-3 w-5/6 rounded bg-muted" />
                  </div>
                  <div className="h-8 w-28 rounded bg-muted" />
                </div>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              {[1, 2, 3].map((i) => (
                <div key={i} className="product-panel border border-border/60 bg-background/72 p-5">
                  <div className="space-y-3">
                    <div className="h-3 w-24 rounded bg-muted" />
                    <div className="h-6 w-32 rounded bg-muted" />
                    <div className="space-y-2">
                      <div className="h-3 w-full rounded bg-muted" />
                      <div className="h-3 w-2/3 rounded bg-muted" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pt-4 sm:px-8">
        <div className="h-[10px] w-24 rounded bg-muted mb-3" />
        <div className="grid gap-4 xl:grid-cols-2">
          {[1, 2].map((i) => (
            <div key={i} className="product-panel border border-border/60 bg-background/72 p-5">
              <div className="space-y-3">
                <div className="h-3 w-20 rounded bg-muted" />
                <div className="h-7 w-36 rounded bg-muted" />
                <div className="space-y-2">
                  <div className="h-3 w-full rounded bg-muted" />
                  <div className="h-3 w-5/6 rounded bg-muted" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="px-4 pt-4 sm:px-8">
        <div className="product-panel border border-emerald-500/20 bg-emerald-500/6 px-4 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="h-3 w-28 rounded bg-muted" />
              <div className="h-3 w-56 rounded bg-muted" />
            </div>
            <div className="flex gap-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-7 w-24 rounded bg-muted" />
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pt-5 sm:px-8">
        <div className="product-panel p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="h-[10px] w-24 rounded bg-muted" />
            <div className="h-8 w-24 rounded bg-muted" />
          </div>
          <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
            {[1, 2, 3].map((i) => (
              <div key={i} className="product-panel w-64 h-[140px] shrink-0 border border-border/60 bg-background/72 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="h-3 w-12 bg-muted rounded" />
                  <div className="h-5 w-14 bg-muted rounded" />
                </div>
                <div className="space-y-1.5">
                  <div className="h-3 w-full bg-muted rounded" />
                  <div className="h-3 w-5/6 bg-muted rounded" />
                  <div className="h-3 w-2/3 bg-muted rounded" />
                </div>
                <div className="border-t border-border/50 pt-3">
                  <div className="h-2.5 w-28 bg-muted rounded" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="px-4 pt-6 pb-8 flex-1 sm:px-8">
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="product-panel p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="h-[10px] w-24 rounded bg-muted" />
              <div className="h-8 w-20 rounded bg-muted" />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="h-[210px] border border-border/70 bg-background/72 p-4 flex flex-col gap-3">
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
                  <div className="space-y-2 mt-auto border-t border-border/60 pt-3">
                    <div className="flex justify-between">
                      <div className="h-[10px] w-20 bg-muted rounded" />
                      <div className="h-[12px] w-10 bg-muted rounded" />
                    </div>
                    <div className="h-[10px] w-4/5 bg-muted rounded" />
                    <div className="h-[10px] w-2/3 bg-muted rounded" />
                    <div className="h-7 w-20 bg-muted rounded mt-2" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="product-panel p-4 sm:p-5">
                <div className="space-y-3">
                  <div className="h-[10px] w-28 rounded bg-muted" />
                  <div className="h-8 w-32 rounded bg-muted" />
                  <div className="grid grid-cols-3 gap-2">
                    {[1, 2, 3].map((j) => (
                      <div key={j} className="h-14 rounded border border-border/60 bg-background/60" />
                    ))}
                  </div>
                  <div className="space-y-2 border-t border-border/60 pt-3">
                    <div className="h-3 w-full rounded bg-muted" />
                    <div className="h-3 w-4/5 rounded bg-muted" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
