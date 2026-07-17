import { notFound } from "next/navigation";
import Link from "next/link";
import { LegalPage, LegalSection, P, L, Fill, Strong } from "../../_mkt/legal";
import { mk } from "../../_mkt/tokens";

export const metadata = {
  title: "Terms of Service · penKeep",
};

export default function TermsPage() {
  notFound();
  return (
    <LegalPage
      kicker="Legal"
      title={<>Terms of Service</>}
      updated="6 June 2026"
      intro={
        <>
          These terms are a binding agreement between you and{" "}
          <Fill>[LEGAL ENTITY NAME]</Fill> (&ldquo;penKeep&rdquo;,
          &ldquo;we&rdquo;, &ldquo;us&rdquo;). By creating an account, joining the founding
          presale, or using the site, you agree to them. If you don&apos;t agree, please
          don&apos;t use penKeep.
        </>
      }
    >
      <LegalSection n="01" title="What penKeep is — and is not">
        <P>
          penKeep is a <Strong>research and journaling tool</Strong>. You write down the reasons
          you hold an investment, and we monitor public information — earnings, filings, news and
          similar — against what you wrote, and tell you when something appears to test it.
        </P>
        <P>
          <Strong>
            penKeep is not a financial adviser, investment adviser, broker-dealer, or fiduciary,
            and nothing we provide is financial, investment, legal or tax advice.
          </Strong>{" "}
          We never tell you to buy, hold or sell. Thesis health scores, alerts and digests are
          prompts to re-read your own reasoning, not instructions to act. Every decision is yours,
          and you are solely responsible for it. Investing carries risk, including loss of capital.
        </P>
      </LegalSection>

      <LegalSection n="02" title="Eligibility">
        <P>
          You must be at least 18 years old and able to form a binding contract in your country of
          residence. You are responsible for complying with any laws that apply to you, including
          where penKeep is available in your jurisdiction.
        </P>
      </LegalSection>

      <LegalSection n="03" title="Your account">
        <P>
          You are responsible for keeping your login credentials secure and for activity under your
          account. Tell us promptly at{" "}
          <a href="mailto:support@penkeep.io" style={{ color: mk.accent }}>support@penkeep.io</a>{" "}
          if you suspect unauthorised access. You agree to give accurate information and keep it up
          to date.
        </P>
      </LegalSection>

      <LegalSection n="04" title="The founding-member presale">
        <P>
          The founding presale lets you pre-purchase access to penKeep Premium before public
          launch, at a founding rate that stays locked while your membership remains active. By completing
          checkout you understand and agree that:
        </P>
        <L
          items={[
            <>
              <Strong>The product is still in development.</Strong> Premium features are described
              on our pricing page as planned, and may change before launch. We&apos;ll deliver
              access before the public launch and email you when your account is ready.
            </>,
            <>
              <Strong>Your founding price is locked</Strong> for as long as your membership stays
              active, on the terms shown at the time of purchase.
            </>,
            <>
              <Strong>You can get a full refund at any time until we launch your access</Strong>, no
              reason needed — see our{" "}
              <Link href="/refunds" style={{ color: mk.accent }}>
                Refund &amp; Cancellation Policy
              </Link>
              .
            </>,
            <>
              <Strong>If we never launch</Strong> the Premium product, or discontinue penKeep before
              delivering your access, you are entitled to a full refund of what you paid.
            </>,
          ]}
        />
        <P>
          Payments are processed by <Strong>Stripe</Strong>. We never receive or store your full
          card details. Prices are shown in GBP and, where applicable, exclusive of taxes that are
          added at checkout.
        </P>
      </LegalSection>

      <LegalSection n="05" title="Brokerage connections">
        <P>
          If you choose to connect a brokerage, the connection is <Strong>read-only</Strong>: we
          read your positions to decide which signals are relevant to you. We never place trades,
          move money, or access your funds. You can disconnect at any time. You are responsible for
          complying with your broker&apos;s own terms.
        </P>
      </LegalSection>

      <LegalSection n="06" title="Acceptable use">
        <P>You agree not to:</P>
        <L
          items={[
            "Use penKeep for anything unlawful, or in breach of securities or market-abuse laws.",
            "Resell, scrape, reverse-engineer, or build a competing dataset from our outputs.",
            "Attempt to disrupt, overload, or gain unauthorised access to our systems.",
            "Misrepresent penKeep's outputs as financial advice to others.",
          ]}
        />
      </LegalSection>

      <LegalSection n="07" title="Intellectual property">
        <P>
          The site, software, and our original content are owned by penKeep and protected by law.
          We grant you a limited, personal, non-transferable licence to use penKeep for your own
          investing. <Strong>Your thesis notes and the content you create remain yours.</Strong> You
          grant us only the licence we need to operate the service for you (for example, to process
          your notes through our monitoring pipeline) — see our{" "}
          <Link href="/privacy" style={{ color: mk.accent }}>
            Privacy Policy
          </Link>
          .
        </P>
      </LegalSection>

      <LegalSection n="08" title="AI and data">
        <P>
          We use AI to analyse public market information against your thesis claims. We do not use
          your notes or financial reasoning to train any AI model. See our{" "}
          <Link href="/privacy" style={{ color: mk.accent }}>
            Privacy Policy
          </Link>{" "}
          for full details on how we use AI providers and what commitments they have made.
        </P>
      </LegalSection>

      <LegalSection n="09" title="Disclaimers">
        <P>
          penKeep is provided <Strong>&ldquo;as is&rdquo; and &ldquo;as available&rdquo;</Strong>.
          We rely on third-party data (market data, news, filings) and AI models that can be
          incomplete, delayed, or wrong. We don&apos;t warrant that outputs are accurate, complete,
          or suitable for any purpose, or that the service will be uninterrupted or error-free. You
          should independently verify anything before acting on it.
        </P>
      </LegalSection>

      <LegalSection n="10" title="Limitation of liability">
        <P>
          To the maximum extent permitted by law, penKeep is not liable for any investment losses,
          lost profits, or indirect, incidental or consequential damages arising from your use of
          the service. Our total liability to you for any claim is limited to the greater of the
          amount you paid us in the 12 months before the claim, or £100. Nothing in these terms
          excludes liability that cannot lawfully be excluded (such as for fraud or death/personal
          injury caused by negligence). <Strong>Your statutory consumer rights are not
          affected.</Strong>
        </P>
      </LegalSection>

      <LegalSection n="11" title="Indemnity">
        <P>
          You agree to indemnify penKeep against claims and costs arising from your misuse of the
          service or breach of these terms.
        </P>
      </LegalSection>

      <LegalSection n="12" title="Changes and termination">
        <P>
          We may update the service and these terms. If a change is material, we&apos;ll give
          reasonable notice (for example by email or on the site); continued use after that means
          you accept the change. You may stop using penKeep and close your account at any time. We
          may suspend or terminate accounts that breach these terms, and — for paid founding members
          — will handle any refund due under our Refund Policy.
        </P>
      </LegalSection>

      <LegalSection n="13" title="Governing law">
        <P>
          These terms are governed by the laws of England and Wales, and the courts of England and
          Wales have non-exclusive jurisdiction. If you are a consumer, you may also have the right
          to bring claims in your country of residence.
        </P>
      </LegalSection>

      <LegalSection n="14" title="Contact">
        <P>
          Questions about these terms? Email{" "}
          <a href="mailto:legal@penkeep.io" style={{ color: mk.accent }}>legal@penkeep.io</a>.
          Our registered details are <Fill>[LEGAL ENTITY NAME, COMPANY NUMBER, REGISTERED ADDRESS]</Fill>.
        </P>
      </LegalSection>
    </LegalPage>
  );
}
