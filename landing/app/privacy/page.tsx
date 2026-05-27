import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy — koreanpulse",
  description:
    "How koreanpulse collects, uses, retains, and discloses personal data, including PIPA (Korea) and GDPR (EU) compliance.",
};

const LAST_UPDATED = "2026-05-27";

export default function PrivacyPage() {
  return (
    <main className="min-h-screen px-6 py-16 sm:px-10 lg:px-16">
      <div className="mx-auto max-w-3xl">
        <header className="mb-10 text-zinc-300">
          <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-100">
            ← back to koreanpulse.dev
          </Link>
          <h1 className="mt-4 text-3xl font-bold text-zinc-100">
            Privacy Policy
          </h1>
          <p className="mt-2 text-sm text-zinc-500">
            Last updated: {LAST_UPDATED}
          </p>
        </header>

        <article className="prose prose-invert prose-sm max-w-none text-zinc-300 space-y-6 leading-relaxed">
          <section>
            <p>
              koreanpulse (&quot;we&quot;, &quot;us&quot;, &quot;the
              service&quot;) operates the website at{" "}
              <a href="https://koreanpulse.dev" className="text-accent">
                koreanpulse.dev
              </a>{" "}
              and the related MCP server distribution. This policy covers how
              we collect, use, retain, and disclose personal data in
              compliance with the Republic of Korea&apos;s Personal Information
              Protection Act (PIPA) and the EU/EEA General Data Protection
              Regulation (GDPR).
            </p>
            <p>
              For users in California, this document also serves as our notice
              under the California Consumer Privacy Act (CCPA).
            </p>
          </section>

          <h2 className="text-xl font-semibold text-zinc-100">
            1. Personal data we collect
          </h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Email address</strong> — when you join the launch
              waitlist or contact us. Required to deliver the service or
              communication you requested.
            </li>
            <li>
              <strong>Self-described role</strong> (analyst, rotator,
              diaspora, journalist, developer, other) — optional, only if you
              select it on the waitlist form. Used to size audience segments
              in aggregate.
            </li>
            <li>
              <strong>Payment metadata</strong> — when you purchase a paid
              plan: name, country, last four card digits, plan, subscription
              status. The full payment instrument is held by Polar Software
              Inc. (our merchant of record); we receive only the metadata
              fields above.
            </li>
            <li>
              <strong>License-key usage</strong> — period_calls counter and
              period_started_at timestamp, tied to your license key. Used to
              enforce the per-tier query cap.
            </li>
            <li>
              <strong>Server logs</strong> — Cloudflare records IP, user
              agent, request path, and response code as part of normal
              operation. Retained 30 days.
            </li>
          </ul>
          <p>
            We do <strong>not</strong> use cookies for tracking. We do{" "}
            <strong>not</strong> embed third-party analytics, ad pixels, or
            social media trackers on the marketing site.
          </p>
          <p>
            <strong>MCP tool inputs and outputs are stateless.</strong> The
            license key is the only user-provided identifier and is validated
            server-side; it is not echoed back in tool responses. Tool
            responses contain only the requested market or filing data and do
            not include user identifiers, diagnostic debug codes, or session
            metadata. We do not collect or retain personally identifiable
            information through MCP tool invocations.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            2. Why we collect it (purposes &amp; lawful basis)
          </h2>
          <table className="w-full text-sm">
            <thead className="text-zinc-400">
              <tr>
                <th className="text-left pr-4 pb-2">Data</th>
                <th className="text-left pr-4 pb-2">Purpose</th>
                <th className="text-left pb-2">Lawful basis (GDPR)</th>
              </tr>
            </thead>
            <tbody className="text-zinc-300">
              <tr>
                <td className="pr-4 py-1">Email (waitlist)</td>
                <td className="pr-4 py-1">Single launch announcement</td>
                <td className="py-1">Consent (Art. 6(1)(a))</td>
              </tr>
              <tr>
                <td className="pr-4 py-1">Email (paid customer)</td>
                <td className="pr-4 py-1">
                  Service delivery, billing notifications
                </td>
                <td className="py-1">Contract (Art. 6(1)(b))</td>
              </tr>
              <tr>
                <td className="pr-4 py-1">Payment metadata</td>
                <td className="pr-4 py-1">License issuance &amp; validation</td>
                <td className="py-1">Contract (Art. 6(1)(b))</td>
              </tr>
              <tr>
                <td className="pr-4 py-1">License-key usage</td>
                <td className="pr-4 py-1">Per-tier quota enforcement</td>
                <td className="py-1">Contract (Art. 6(1)(b))</td>
              </tr>
              <tr>
                <td className="pr-4 py-1">Server logs</td>
                <td className="pr-4 py-1">Security, abuse mitigation</td>
                <td className="py-1">Legitimate interest (Art. 6(1)(f))</td>
              </tr>
            </tbody>
          </table>

          <h2 className="text-xl font-semibold text-zinc-100">
            3. Retention periods
          </h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Waitlist email</strong>: until launch announcement is
              sent, or you unsubscribe (whichever first). Maximum 24 months.
            </li>
            <li>
              <strong>Paid customer records</strong>: 5 years after the last
              transaction, as required by Korean tax and commerce law (전자
              상거래법 §6, 부가가치세법).
            </li>
            <li>
              <strong>License usage counters</strong>: cleared at the end of
              each billing period; aggregate totals retained 24 months.
            </li>
            <li>
              <strong>Server logs</strong>: 30 days, then automatically
              deleted by Cloudflare.
            </li>
          </ul>

          <h2 className="text-xl font-semibold text-zinc-100">
            4. Third parties we share data with (sub-processors)
          </h2>
          <p>
            We do not sell or rent personal data. We share the minimum
            necessary with the following processors to operate the service:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Polar Software Inc.</strong> (USA, polar.sh) — payment
              processing (merchant of record). Receives full payment
              instrument; we receive only metadata (name, country, last four
              card digits, plan, subscription status).
            </li>
            <li>
              <strong>Cloudflare, Inc.</strong> (USA) — hosting, DNS, KV
              storage, license database (D1). Receives all service traffic.
            </li>
            <li>
              <strong>Vercel, Inc.</strong> (USA) — landing page hosting.
              Receives marketing-site visit logs only.
            </li>
            <li>
              <strong>OpenAI, LLC</strong> (USA) — translation and
              summarisation of Korean source text. Receives the Korean text
              you submit via the MCP server. Per OpenAI&apos;s API terms, this
              data is not used to train models.
            </li>
          </ul>
          <p>
            Each of these sub-processors maintains its own privacy and
            security commitments. International transfers (Korea → USA / EU →
            USA) rely on Standard Contractual Clauses where applicable.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            5. Your rights
          </h2>
          <p>
            Under PIPA, GDPR, and CCPA you may request to:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>access the personal data we hold about you;</li>
            <li>correct inaccurate data;</li>
            <li>delete your data (right to be forgotten);</li>
            <li>restrict or object to processing;</li>
            <li>obtain a copy of your data in a portable format;</li>
            <li>
              not be subject to a decision based solely on automated
              processing (we do not perform such automated decisions);
            </li>
            <li>withdraw consent at any time without affecting prior
              processing.</li>
          </ul>
          <p>
            To exercise any of these rights, email{" "}
            <a href="mailto:privacy@koreanpulse.dev" className="text-accent">
              privacy@koreanpulse.dev
            </a>
            . We will respond within 30 days. If you are an EU resident, you
            also have the right to lodge a complaint with your local
            supervisory authority.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            6. Data Protection Officer / 개인정보 보호책임자 (CPO)
          </h2>
          <p>
            koreanpulse is operated by an individual founder. The contact
            point for all data-protection matters, in both Korean and English,
            is the email above. Korean users may also reach the Personal
            Information Protection Commission (개인정보보호위원회) at{" "}
            <a
              href="https://www.privacy.go.kr"
              className="text-accent"
              target="_blank"
              rel="noopener noreferrer"
            >
              privacy.go.kr
            </a>{" "}
            for any unresolved complaint.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            7. Security
          </h2>
          <p>
            All traffic is TLS 1.2+. License keys are stored hashed. Payment
            credentials never reach our servers (handled by Polar). We
            disclose any confirmed personal-data breach to affected users
            and to the relevant supervisory authority within 72 hours, as
            required by GDPR Art. 33 and PIPA §34.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            8. Children
          </h2>
          <p>
            koreanpulse is not directed to children under 14 (PIPA threshold)
            or under 16 (GDPR threshold). We do not knowingly collect data
            from minors. If you believe we have, contact us and we will
            delete it.
          </p>

          <h2 className="text-xl font-semibold text-zinc-100">
            9. Changes to this policy
          </h2>
          <p>
            We will notify users of material changes at least 30 days in
            advance via the email associated with their account, and post the
            updated policy at this URL. Continued use after the effective
            date constitutes acceptance.
          </p>
        </article>

        <footer className="mt-16 border-t border-zinc-800 pt-6 text-xs text-zinc-500">
          <Link href="/" className="hover:text-zinc-300">
            ← koreanpulse.dev
          </Link>
          <span className="mx-2">·</span>
          <Link href="/terms" className="hover:text-zinc-300">
            Terms of Service
          </Link>
        </footer>
      </div>
    </main>
  );
}
