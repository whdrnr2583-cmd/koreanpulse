import { redirect } from "next/navigation";

export const metadata = {
  title: "Pricing — koreanpulse",
  description:
    "Cloud Solo $29/mo, Analyst $79/mo, Desk $249/mo. OSS self-host available. English-first Korean equity intelligence MCP for Claude Desktop, Cursor, ChatGPT, and FastMCP trading agents.",
  alternates: { canonical: "https://koreanpulse.dev/#pricing" },
};

export default function PricingPage() {
  redirect("/#pricing");
}
