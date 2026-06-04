import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="product-shell">
        <div aria-hidden className="product-shell-glow" />
        <Navbar />
        <main className="product-main">{children}</main>
      </div>
    </AuthGuard>
  );
}
