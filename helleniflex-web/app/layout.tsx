import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HelleniFlex · Battery Arbitrage",
  description: "MILP battery dispatch optimizer for the Greek Day-Ahead Market",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#060e1d] antialiased">{children}</body>
    </html>
  );
}
