import { ImageResponse } from "next/og";

// Site-wide Open Graph / Twitter card image. Next.js auto-wires this into
// metadata for every route that has no opengraph-image of its own.
export const alt = "koreanpulse — Korean equity intelligence MCP";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#0E1116",
          padding: "80px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          <svg width="56" height="56" viewBox="0 0 64 64">
            <polyline
              points="6,32 18,32 22,18 27,46 32,12 37,52 42,28 46,32 58,32"
              stroke="#F0B429"
              strokeWidth="4"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span
            style={{
              marginLeft: "18px",
              fontSize: "38px",
              fontWeight: 600,
              color: "#E4E4E7",
            }}
          >
            koreanpulse
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              fontSize: "66px",
              fontWeight: 700,
              lineHeight: 1.15,
              color: "#FAFAFA",
            }}
          >
            Korean equity intelligence,
          </div>
          <div
            style={{
              fontSize: "66px",
              fontWeight: 700,
              lineHeight: 1.15,
              color: "#F0B429",
            }}
          >
            as an MCP server.
          </div>
          <div
            style={{
              fontSize: "29px",
              color: "#A1A1AA",
              marginTop: "30px",
              lineHeight: 1.4,
            }}
          >
            DART filings · KOSPI/KOSDAQ disclosures · foreign-holder &amp;
            activist 5%-rule flows — translated to English.
          </div>
        </div>

        <div style={{ display: "flex", fontSize: "25px", color: "#71717A" }}>
          koreanpulse.dev · for ChatGPT, Claude.ai &amp; Cursor
        </div>
      </div>
    ),
    { ...size },
  );
}
