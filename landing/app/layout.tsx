import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const SITE = "https://koreanpulse.dev";
const DESCRIPTION =
  "Real-time Korean stock market intelligence for AI assistants — track DART " +
  "filings, foreign & activist investor activity, and classified Korean " +
  "industry news, in English. MCP server for ChatGPT, Claude, and Cursor.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title:
    "koreanpulse — Korean Stock Market Intelligence for AI assistants (DART, KOSPI/KOSDAQ)",
  description: DESCRIPTION,
  keywords: [
    "Korean stock market data",
    "Korean stocks",
    "track Korean DART filings",
    "DART API in English",
    "KOSPI",
    "KOSDAQ",
    "MCP server for Korean stocks",
    "Korean activist investor tracking",
    "foreign investor activity Korean stocks",
    "Korean market data for AI agents",
  ],
  alternates: { canonical: SITE },
  openGraph: {
    title: "koreanpulse — Korean Stock Market Intelligence for AI assistants",
    description: DESCRIPTION,
    type: "website",
    url: SITE,
    siteName: "koreanpulse",
  },
  twitter: {
    card: "summary",
    title: "koreanpulse — Korean Stock Market Intelligence for AI assistants",
    description: DESCRIPTION,
  },
};

const organizationLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "koreanpulse",
  url: SITE,
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "koreanpulse",
  applicationCategory: "FinanceApplication",
  operatingSystem: "MCP client — ChatGPT, Claude.ai, Cursor, Claude Desktop",
  url: SITE,
  description:
    "Korean stock market intelligence MCP server for AI assistants — track DART " +
    "(전자공시) filings, foreign investor activity, activist investor campaigns, and " +
    "KOSPI/KOSDAQ disclosures, with classified Korean industry news, all in English.",
  featureList: [
    "DART filing tracking with English translation",
    "Korean activist investor 5%-rule classification (KCGI, Align, ValueAct, Elliott)",
    "Foreign-holder 5%-rule flow tracking (BlackRock, Vanguard, Norges, GIC, Temasek)",
    "Korean industry news across 16 sectors",
  ],
  offers: [
    { "@type": "Offer", name: "Cloud Solo", price: "29", priceCurrency: "USD" },
    { "@type": "Offer", name: "Cloud Analyst", price: "79", priceCurrency: "USD" },
    { "@type": "Offer", name: "Cloud Desk", price: "249", priceCurrency: "USD" },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {children}
        <Analytics />
      </body>
    </html>
  );
}
