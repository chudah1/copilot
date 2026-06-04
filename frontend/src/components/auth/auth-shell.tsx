import type { ReactNode } from "react";

interface AuthAsideItem {
  eyebrow: string;
  title: string;
  body: string;
}

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  footer,
  asideHeading,
  asideBody,
  asideItems,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  asideHeading: string;
  asideBody: string;
  asideItems: AuthAsideItem[];
}) {
  return (
    <div className="product-shell">
      <div className="product-shell-glow" />
      <main className="product-main flex min-h-screen items-center px-4 py-10 sm:px-8">
        <div className="mx-auto grid w-full max-w-5xl gap-5 lg:grid-cols-[minmax(0,30rem)_minmax(18rem,22rem)] lg:items-center">
          <section className="product-panel product-panel-muted p-6 sm:p-8">
            <div className="space-y-6">
              <div className="space-y-4 border-b border-border/60 pb-5">
                <div className="flex items-start justify-between gap-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                    penKeep
                  </p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
                    {eyebrow}
                  </p>
                </div>

                <div className="space-y-2">
                  <h1 className="font-display italic text-[2.2rem] leading-tight text-foreground sm:text-[2.6rem]">
                    {title}
                  </h1>
                  {description && (
                    <p className="max-w-lg font-sans text-sm leading-relaxed text-muted-foreground">
                      {description}
                    </p>
                  )}
                </div>
              </div>

              {children}

              {footer && <div className="border-t border-border/60 pt-4">{footer}</div>}
            </div>
          </section>

          <aside className="space-y-4">
            <div className="product-panel p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                {asideHeading}
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                {asideBody}
              </p>
            </div>

            {asideItems.map((item) => (
              <div key={item.title} className="product-panel p-5">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  {item.eyebrow}
                </p>
                <p className="mt-2 font-display text-[1.3rem] italic leading-tight text-foreground">
                  {item.title}
                </p>
                <p className="mt-2 font-sans text-sm leading-relaxed text-muted-foreground">
                  {item.body}
                </p>
              </div>
            ))}
          </aside>
        </div>
      </main>
    </div>
  );
}
