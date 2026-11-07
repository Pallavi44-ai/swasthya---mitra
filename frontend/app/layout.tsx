import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: "Swasthya Mitra – voice-enabled health companion",
  description: "A support tool for health information, prescription reading and medicine reminders in English, Hindi, Kannada and Telugu. Not a substitute for a doctor.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
