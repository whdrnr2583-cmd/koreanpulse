import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service — koreanpulse",
  description:
    "Terms of service for koreanpulse, including service definition, license use, refunds, and the data-only / no-investment-advice disclaimer.",
};

const LAST_UPDATED = "2026-07-19";

export default function TermsPage() {
  return (
    <main className="min-h-screen px-6 py-16 sm:px-10 lg:px-16">
      <div className="mx-auto max-w-3xl">
        <header className="mb-10 text-zinc-300">
          <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-100">
            ← back to koreanpulse.dev
          </Link>
          <h1 className="mt-4 text-3xl font-bold text-zinc-100">
            Terms of Service
          </h1>
          <p className="mt-2 text-sm text-zinc-500">
            Last updated: {LAST_UPDATED}
          </p>
        </header>

        <article className="prose prose-invert prose-sm max-w-none text-zinc-300 space-y-6 leading-relaxed">
          <section className="rounded-md border border-amber-700/50 bg-amber-500/5 p-4">
            <p className="text-sm text-amber-200 font-semibold">
              Important — not investment advice.
            </p>
            <p className="mt-2 text-sm text-zinc-300">
              koreanpulse provides translated and classified primary-source
              data from Korean public filings (DART) and Korean industry
              news. It is <strong>not investment advice</strong> and does
              not constitute a recommendation to buy, sell, or hold any
              security. The service performs no individualized analysis or
              personalized recommendation. All output is general data
              routing intended for informational purposes only. You are
              responsible for your own investment decisions and should
              consult a licensed financial advisor where appropriate.
            </p>
            <p className="mt-3 text-xs text-zinc-400">
              koreanpulse는 한국 공시시스템(DART) 및 한국 산업 뉴스의 1차
              자료를 영어로 번역·분류하여 제공하는 데이터 서비스입니다.
              본 서비스는 투자자문 또는 투자권유에 해당하지 않으며, 특정
              증권의 매수·매도·보유에 대한 권유를 구성하지 않습니다.
              모든 투자 판단은 사용자 본인의 책임이며, 필요 시 자격을
              갖춘 금융투자업자에게 자문을 구하시기 바랍니다.
            </p>
          </section>

          <h2 className="text-xl font-semibold text-zinc-100">
            1. Acceptance
          </h2>
          <p>
            By using koreanpulse — including the public daily snapshot at{" "}
            <code>/today</code>, the MCP server, or any paid plan — you agree
            to these terms and to our{" "}
            <Link href="/privacy" className="text-accent">
              Privacy Policy
            </Link>
            . If you do not agree, do not use the service.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            2. What koreanpulse is
          </h2>
          <p>
            koreanpulse is a data and translation layer for Korean
            equities — primary-source DART filings, foreign-holder 5%-rule
            disclosures, Korean activist filings, and Korean industry news,
            translated and classified into English on demand. Two surfaces:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Free public snapshot</strong> at{" "}
              <Link href="/today" className="text-accent">/today</Link> — no
              account, no key, no warranty.
            </li>
            <li>
              <strong>Paid Cloud subscription</strong> — license key issued
              by our webhook on successful Polar purchase. Tiers listed on
              the homepage.
            </li>
          </ul>
          <p>
            Source code (the engine) is published under AGPL-3.0 at
            github.com/whdrnr2583-cmd/koreanpulse for self-hosters. The
            hosted Cloud service is a separate commercial offering.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            3. Eligibility
          </h2>
          <p>
            You must be 18 years of age or older and legally permitted to use
            financial information services in your jurisdiction. By using the
            service you represent that this is the case.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            4. Account &amp; license
          </h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              A license key is bound to one user (Cloud Solo / Analyst) or
              the agreed seat count (Cloud Desk).
            </li>
            <li>
              Sharing or reselling a license key violates these terms and
              voids the license.
            </li>
            <li>
              We may revoke a license key on confirmed abuse, with a refund
              for any remaining prepaid period.
            </li>
          </ul>

          <h2 className="text-xl font-semibold text-zinc-100">
            5. Payment, billing, and refunds
          </h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              All payments are processed by Polar Software Inc. (polar.sh)
              as the merchant of record. Polar&apos;s terms apply to the
              payment transaction itself.
            </li>
            <li>
              Subscriptions auto-renew monthly until cancelled. You can
              cancel any time from the Polar customer portal; access
              continues to the end of the paid period.
            </li>
            <li>
              <strong>30-day refund window</strong>: if the service does not
              fit your needs, request a refund within 30 days of the first
              payment for a full refund, no questions asked.
            </li>
            <li>
              Beta status is disclosed plainly on the pricing page. Several
              tier features (watchlist polling, alert dispatch, multi-channel
              alerts, archive retention windows, seat enforcement) are
              planned and not yet available. Subscribing starts a paid
              monthly subscription immediately; what you receive today is
              described in the &quot;Available now&quot; section of the
              pricing page. If a planned feature you subscribed for is
              delayed, the 30-day refund window above applies, and you can
              cancel at any time.
            </li>
          </ul>

          <h2 className="text-xl font-semibold text-zinc-100">
            6. Service availability &amp; warranty disclaimer
          </h2>
          <p>
            The service is provided on an &quot;as is&quot; and &quot;as
            available&quot; basis. We make no warranty as to availability,
            uptime, accuracy, completeness, or fitness for a particular
            purpose. We do not guarantee any specific outcome or trading
            result. Cloud Desk customers may negotiate a written SLA on
            request; absent such an agreement, no SLA exists.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            7. Acceptable use
          </h2>
          <p>You agree not to:</p>
          <ul className="list-disc pl-6 space-y-1">
            <li>share, resell, or sub-license your license key;</li>
            <li>
              scrape or systematically download the public daily snapshot in
              a way that imposes unreasonable load on our infrastructure;
            </li>
            <li>reverse-engineer the hosted services;</li>
            <li>
              use the service in violation of Korean Capital Markets Act
              (자본시장과 금융투자업에 관한 법률), Korean securities
              regulations, or comparable laws in your jurisdiction;
            </li>
            <li>
              redistribute the source data (DART filings, Korean news
              summaries) as a competing English news service.
            </li>
          </ul>

          <h2 className="text-xl font-semibold text-zinc-100">
            8. Intellectual property
          </h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Code (engine)</strong> is licensed under AGPL-3.0.
              Self-hosters must comply with the AGPL, including its network
              copyleft (§13).
            </li>
            <li>
              <strong>Hosted-service data</strong> — including curated
              foreign-holder and activist allowlists, the daily English
              digest, and the translation cache — is the proprietary work of
              koreanpulse. Subscribing to a Cloud plan grants you a personal,
              revocable, non-exclusive licence to use this data for your own
              research; you may not republish it as a competing news service.
            </li>
            <li>
              <strong>Source data</strong> from DART is retrieved through the
              DART open API operated by the Financial Supervisory Service;
              underlying filings remain subject to their own applicable
              rules, and each item links back to the original filing with
              attribution. Korean news items are used as short summaries
              with attribution and outbound links only — no full-text
              republication. Users who redistribute data downstream should
              assess the licensing, data-use, and financial-services
              obligations that apply in their own jurisdiction and use case.
            </li>
          </ul>

          <h2 className="text-xl font-semibold text-zinc-100">
            9. Limitation of liability
          </h2>
          <p>
            To the maximum extent permitted by law, koreanpulse and its
            operator shall not be liable for any indirect, incidental,
            consequential, special, exemplary, or punitive damages, or for
            lost profits, lost data, or trading losses, arising from your use
            of or inability to use the service. Our total liability for any
            claim shall not exceed the amount you paid to us in the
            twelve (12) months preceding the claim. Some jurisdictions do not
            allow these limitations; in that case the above applies to the
            extent permitted.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            10. Indemnification
          </h2>
          <p>
            You agree to indemnify koreanpulse against any claim arising from
            your breach of these terms, your use of the service, or your
            violation of any third-party right or applicable law.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            11. Termination
          </h2>
          <p>
            You may terminate at any time by cancelling your subscription. We
            may terminate or suspend access for material breach of these
            terms (notably §7), with refund of any unused prepaid period.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            12. Governing law &amp; venue
          </h2>
          <p>
            These terms are governed by the laws of the Republic of Korea,
            without regard to conflict-of-laws principles. The Seoul Central
            District Court (서울중앙지방법원) shall have exclusive
            jurisdiction for disputes between koreanpulse and a Korean-
            resident user. For non-Korean-resident users, payment-related
            disputes are subject to Polar&apos;s terms; all other disputes
            are subject to the courts of Seoul, Korea.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            13. Changes
          </h2>
          <p>
            We may revise these terms; material revisions will be posted at
            this URL with the new effective date and announced 30 days in
            advance to active customers. Continued use after the effective
            date constitutes acceptance.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            14. Contact
          </h2>
          <p>
            Questions:{" "}
            <a href="mailto:legal@koreanpulse.dev" className="text-accent">
              legal@koreanpulse.dev
            </a>
            . Privacy and data-protection questions:{" "}
            <a href="mailto:privacy@koreanpulse.dev" className="text-accent">
              privacy@koreanpulse.dev
            </a>
            .
          </p>
        </article>

        <footer className="mt-16 border-t border-zinc-800 pt-6 text-xs text-zinc-500">
          <Link href="/" className="hover:text-zinc-300">
            ← koreanpulse.dev
          </Link>
          <span className="mx-2">·</span>
          <Link href="/privacy" className="hover:text-zinc-300">
            Privacy Policy
          </Link>
        </footer>
      </div>
    </main>
  );
}
