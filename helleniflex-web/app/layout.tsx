import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Helios · Greek Battery Analysis",
  description: "Day-ahead battery dispatch analysis for the Greek electricity market",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-aegean-950 antialiased">{children}</body>
    </html>
  );
}
