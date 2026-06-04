import Link from "next/link";
import { LegalPage, LegalSection, P, L, Fill, Strong } from "../../_mkt/legal";
import { mk } from "../../_mkt/tokens";

export const metadata = {
  title: "Refund & Cancellation Policy · penKeep",
};

export default function RefundsPage() {
  return (
    <LegalPage
      kicker="Legal"
      title={
        <>
          Refund &amp;<br />Cancellation Policy
        </>
      }
      updated="3 June 2026"
      intro={
        <>
          We&apos;re asking you to back penKeep before it launches, so we keep refunds simple and
          generous. If it&apos;s not right for you, you get your money back.
        </>
      }
    >
      <LegalSection n="01" title="The founding-member guarantee">
        <P>
          When you join the founding presale, you&apos;re pre-purchasing access to penKeep Premium
          before it&apos;s live. Because of that:
        </P>
        <L
          items={[
            <>
              <Strong>You can request a full refund at any time before we launch your access</Strong>{" "}
              — no reason needed, no questions asked.
            </>,
            <>
              <Strong>If we never launch</Strong> the Premium product, or wind penKeep down before
              delivering your access, we refund you in full automatically.
            </>,
            <>
              <Strong>Your founding price is locked</Strong> for the life of your membership once you
              keep it.
            </>,
          ]}
        />
      </LegalSection>

      <LegalSection n="02" title="Your statutory cooling-off right">
        <P>
          If you&apos;re a consumer in the UK or EU, you normally have a{" "}
          <Strong>14-day right to cancel</Strong> a purchase of digital services for a full refund.
          Our founding guarantee above is more generous than this and runs for longer, but your
          statutory right still applies and is never reduced by this policy.
        </P>
        <P>
          Note: once we&apos;ve delivered your access and you&apos;ve started using the paid service,
          the statutory cooling-off right can end — but our founding guarantee covers you up to the
          point access is delivered.
        </P>
      </LegalSection>

      <LegalSection n="03" title="How to request a refund">
        <P>
          Email <Fill>[support@penkeep.io]</Fill> from the address you used to pay, or reply to your
          receipt. We&apos;ll process the refund to your original payment method, usually within{" "}
          <Fill>[5–10]</Fill> business days. Refunds are issued via Stripe; how quickly it appears
          depends on your bank or card provider.
        </P>
      </LegalSection>

      <LegalSection n="04" title="After launch — subscriptions">
        <P>
          Once penKeep Premium is live and billed as a subscription, you&apos;ll be able to cancel
          any time from your account settings. Cancelling stops future renewals and keeps your access
          until the end of the current paid period. <Fill>[State here whether part-period refunds are
          given — e.g. &ldquo;we don&apos;t refund part-used months, but you keep access until the
          period ends.&rdquo;]</Fill> Founding lifetime members keep their access.
        </P>
      </LegalSection>

      <LegalSection n="05" title="A note on chargebacks">
        <P>
          If something&apos;s wrong, please contact us first — we&apos;ll almost always sort it out
          faster than a chargeback. Opening a chargeback without contacting us can suspend your
          account while the dispute is investigated.
        </P>
      </LegalSection>

      <LegalSection n="06" title="Questions">
        <P>
          Anything unclear? Email <Fill>[support@penkeep.io]</Fill>. See also our{" "}
          <Link href="/terms" style={{ color: mk.accent }}>
            Terms of Service
          </Link>
          .
        </P>
      </LegalSection>
    </LegalPage>
  );
}
