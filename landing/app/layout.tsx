import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "koreanpulse — Get pinged in English when KRX moves on a stock you care about",
  description:
    "Watchlist your KRX tickers; we ping you in English when a 5%-rule filing or material DART event lands. " +
    "Foreign-holder flows, Korean activist filings, industry news — routed to Discord / Telegram / inbox. " +
    "Cloud Solo $29/mo, Analyst $79/mo, Desk $249/mo. OSS self-host available.",
  openGraph: {
    title: "koreanpulse",
    description:
      "Get pinged in English the moment a 5%-rule filing or DART event hits a stock you care about. " +
      "Cloud Solo $29/mo, Analyst $79/mo, Desk $249/mo. OSS self-host available.",
    type: "website",
    url: "https://koreanpulse.dev",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
