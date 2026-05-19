import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <Navbar />
      <main>{children}</main>
    </AuthGuard>
  );
}
