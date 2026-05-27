import { MarketingNav } from "../_mkt/nav";
import { MarketingFooter } from "../_mkt/footer";
import { mk } from "../_mkt/tokens";

export default function MarketingSubLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: mk.paper, color: mk.ink, fontFamily: mk.sans, backgroundImage: "none", minHeight: "100vh" }}>
      <style>{`
        @keyframes mkPulse  { 0%,100%{opacity:.4} 50%{opacity:1} }
        @keyframes mkFadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
        @keyframes mkSlideIn{ from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
      `}</style>
      <MarketingNav />
      {children}
      <MarketingFooter />
    </div>
  );
}
