import Link from "next/link";
import { LegalPage, LegalSection, P, L, Fill, Strong } from "../../_mkt/legal";
import { mk } from "../../_mkt/tokens";

export const metadata = {
  title: "Privacy Policy · penKeep",
};

export default function PrivacyPage() {
  return (
    <LegalPage
      kicker="Legal"
      title={<>Privacy Policy</>}
      updated="6 June 2026"
      intro={
        <>
          This explains what personal data penKeep collects, why, and what rights you have. The
          data controller is <Fill>[LEGAL ENTITY NAME]</Fill>,{" "}
          <Fill>[REGISTERED ADDRESS]</Fill>. For anything privacy-related, email{" "}
          <a href="mailto:privacy@penkeep.io" style={{ color: mk.accent }}>privacy@penkeep.io</a>.
          See also our{" "}
          <Link href="/security" style={{ color: mk.accent }}>
            security page
          </Link>
          .
        </>
      }
    >
      <LegalSection n="01" title="What we collect">
        <L
          items={[
            <>
              <Strong>Account data</Strong> — your email and authentication details (passwords are
              hashed; we never store them in plain text).
            </>,
            <>
              <Strong>Your thesis notes</Strong> — the reasons you write for holding a position, and
              your decisions over time. Encrypted at rest and scoped to your account.
            </>,
            <>
              <Strong>Portfolio data</Strong> — tickers and rough sizing you enter, or positions read
              from a brokerage you connect (read-only). We don&apos;t ingest your trade history.
            </>,
            <>
              <Strong>Preferences</Strong> — alert tone, delivery and quiet-hours settings.
            </>,
            <>
              <Strong>Payment data</Strong> — handled by <Strong>Stripe</Strong>. We receive
              confirmation and limited metadata (such as your email, the amount, and whether payment
              succeeded). <Strong>We never see or store your full card number.</Strong>
            </>,
            <>
              <Strong>Usage &amp; device data</Strong> — basic logs, and limited analytics to keep
              the service working and improve it.
            </>,
          ]}
        />
      </LegalSection>

      <LegalSection n="02" title="How we use it">
        <L
          items={[
            "To provide the service: monitor your theses, generate alerts and digests, and run your account.",
            "To process the founding presale and any future subscription, and send you receipts.",
            "To communicate with you about your account, security, and material changes.",
            "To keep penKeep secure, debug problems, and improve the product.",
          ]}
        />
      </LegalSection>

      <LegalSection n="03" title="Your data is never used to train AI">
        <P>
          <Strong>We do not sell your data. We do not use your thesis notes, portfolio data, or
          financial reasoning to train any AI model — ours or anyone else&apos;s.</Strong>
        </P>
        <P>
          When we process your thesis against market events, we send the minimum context needed to
          the AI provider handling that request. We work exclusively with providers — currently
          Anthropic, OpenAI, and Google — who are contractually bound not to use data submitted
          via the API to train their models.
        </P>
        <P>
          Your notes are a record of your private financial thinking. We treat them accordingly.
        </P>
      </LegalSection>

      <LegalSection n="04" title="Legal bases (UK/EU GDPR)">
        <P>Where GDPR applies, we rely on:</P>
        <L
          items={[
            <>
              <Strong>Contract</Strong> — to deliver the service you signed up for and process your
              purchase.
            </>,
            <>
              <Strong>Legitimate interests</Strong> — to secure, maintain and improve penKeep, kept
              in balance with your rights.
            </>,
            <>
              <Strong>Consent</Strong> — for anything optional (for example, marketing emails), which
              you can withdraw at any time.
            </>,
            <>
              <Strong>Legal obligation</Strong> — to keep records we&apos;re required to keep (such
              as for tax).
            </>,
          ]}
        />
      </LegalSection>

      <LegalSection n="05" title="Who we share it with">
        <P>
          We use a small set of trusted processors who act on our instructions. Each handles only
          what it needs to:
        </P>
        <L
          items={[
            <><Strong>Stripe</Strong> — payment processing.</>,
            <><Strong>Resend</Strong> — transactional and digest emails.</>,
            <><Strong>Railway</Strong> — cloud hosting and database.</>,
            <>
              <Strong>Anthropic, OpenAI, and Google</Strong> — to analyse public market information
              against the claims in your thesis. We send the minimum needed and all three are
              contractually prohibited from using API data to train their models.
            </>,
            <><Strong>Market-data &amp; filing sources</Strong> — to fetch the public information we monitor.</>,
          ]}
        />
        <P>
          We may also disclose data if required by law, or as part of a business transfer, in which
          case we&apos;ll tell you.
        </P>
      </LegalSection>

      <LegalSection n="06" title="International transfers">
        <P>
          Some processors are outside the UK (for example, in the US). Where we transfer personal
          data internationally, we rely on appropriate safeguards such as Standard Contractual
          Clauses.
        </P>
      </LegalSection>

      <LegalSection n="07" title="How long we keep it">
        <P>
          We keep your data while your account is active and as long as needed to provide the
          service. After you delete your account we remove your personal data within a reasonable
          period, except where we must keep limited records (such as payment records for tax) for
          the period required by law.
        </P>
      </LegalSection>

      <LegalSection n="08" title="Your rights">
        <P>
          Depending on where you live, you may have the right to access, correct, delete, export, or
          restrict use of your data, and to object to or withdraw consent for certain processing. To
          exercise any of these, email{" "}
          <a href="mailto:privacy@penkeep.io" style={{ color: mk.accent }}>privacy@penkeep.io</a>{" "}
          — we respond within 30 days (and aim for sooner). You can also complain to your local
          data-protection authority (in the UK, the ICO).
        </P>
      </LegalSection>

      <LegalSection n="09" title="Cookies">
        <P>
          We use the minimum cookies needed to keep you signed in and the site working, plus limited
          analytics. We don&apos;t use advertising cookies or share analytics data with third
          parties for targeting purposes.
        </P>
      </LegalSection>

      <LegalSection n="10" title="Children">
        <P>penKeep is not for anyone under 18, and we don&apos;t knowingly collect their data.</P>
      </LegalSection>

      <LegalSection n="11" title="Changes">
        <P>
          We&apos;ll update this policy as penKeep evolves and revise the date above. If a change is
          material, we&apos;ll give reasonable notice.
        </P>
      </LegalSection>
    </LegalPage>
  );
}
