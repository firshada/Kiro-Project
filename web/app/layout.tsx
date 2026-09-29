import type { Metadata, Viewport } from "next";
import { VT323 } from "next/font/google";
import "./globals.css";

// Self-hosted at build time by next/font; no request to Google at runtime.
const terminal = VT323({ weight: "400", subsets: ["latin"], display: "swap" });

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#050805",
};

export const metadata: Metadata = {
  title: "Scrubby · Data quality terminal",
  description: "Upload a CSV and get a deterministic data quality score and report.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: `${terminal.style.fontFamily}, Consolas, monospace` }}>{children}</body>
    </html>
  );
}
