import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const SITE = "https://koreanpulse.dev";
const DESCRIPTION =
  "English-first Korean equity intelligence MCP — DART filings, KOSPI/KOSDAQ " +
  "disclosures, foreign-holder & activist 5%-rule flows, translated to English.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: "koreanpulse — Korean equity intelligence MCP (DART, KOSPI/KOSDAQ)",
  description: DESCRIPTION,
  keywords: [
    "Korean equity intelligence",
    "Korean stocks",
    "DART filings",
    "KOSPI",
    "KOSDAQ",
    "MCP server",
    "Korean activist investors",
    "foreign-holder 5%-rule disclosure",
    "Korean stock data",
  ],
  alternates: { canonical: SITE },
  openGraph: {
    title: "koreanpulse — Korean equity intelligence MCP",
    description: DESCRIPTION,
    type: "website",
    url: SITE,
    siteName: "koreanpulse",
  },
  twitter: {
    card: "summary",
    title: "koreanpulse — Korean equity intelligence MCP",
    description: DESCRIPTION,
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "koreanpulse",
  applicationCategory: "FinanceApplication",
  operatingSystem: "MCP client — ChatGPT, Claude.ai, Cursor, Claude Desktop",
  url: SITE,
  description:
    "English-first Korean equity intelligence MCP server — DART (전자공시) filings, " +
    "KOSPI/KOSDAQ disclosures, foreign-holder and activist 5%-rule flows, and Korean " +
    "industry news, translated to English on demand.",
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
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {children}
        <Analytics />
      </body>
    </html>
  );
}
