import { Navbar } from "@/components/layout/navbar";

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      <main>{children}</main>
    </>
  );
}
