import type { Metadata } from "next";
import React from "react";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Educational & Research RAG — Document Intelligence Platform",
  description: "Grounded answers over academic research papers, educational datasets, and institutional publications with verifiable citations.",
};

// Next.js / Turbopack dev mode requires eval() for React debugging features.
// unsafe-eval is included only in development; production builds omit it.
const isDev = process.env.NODE_ENV === "development";
const scriptSrc = isDev
  ? "'self' 'unsafe-inline' 'unsafe-eval'"
  : "'self' 'unsafe-inline'";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Rule 7: Content-Security-Policy — tightened in production (no unsafe-eval) */}
        <meta
          httpEquiv="Content-Security-Policy"
          content={`default-src 'self'; script-src ${scriptSrc}; style-src 'self' 'unsafe-inline'; connect-src 'self' http://localhost:8000 ws://localhost:8000; img-src 'self' data:; frame-ancestors 'none';`}
        />
        <meta httpEquiv="X-Content-Type-Options" content="nosniff" />
        <meta httpEquiv="X-Frame-Options" content="DENY" />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
