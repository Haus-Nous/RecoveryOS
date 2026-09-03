import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RecoveryOS — Payment Reliability & Revenue Recovery Control Plane",
  description:
    "Production-oriented financial control plane for payment failure diagnosis, deterministic policy authorization, and verified revenue recovery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased selection:bg-teal-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
