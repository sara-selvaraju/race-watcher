import "@/styles/globals.css";
import type { Metadata } from "next";
import { Shippori_Mincho_B1, Geist, Geist_Mono } from "next/font/google";
import { QueryProvider } from "@/components/QueryProvider";

const display = Shippori_Mincho_B1({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-display",
  display: "swap",
});

const sans = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "競 · Race Watcher · Flemington 2026.06.20",
  description: "Personal race-day dashboard. Heuristic ratings, not financial advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body className="min-h-screen antialiased">
        <QueryProvider>
          <div className="relative z-10">{children}</div>
        </QueryProvider>
        <footer className="relative z-10 border-t border-hairline bg-ink-deep text-xs text-paper-ghost mt-12">
          <div className="mx-auto max-w-6xl px-6 py-5 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="font-display tracking-kanji">責任 · RESPONSIBLE PLAY</span>
            <span className="opacity-50">
              Heuristic ratings — not financial advice. Personal use only.
            </span>
            <span className="ml-auto">
              Gambling Help <a className="text-paper-dim hover:text-gold transition-colors" href="tel:1800858858">1800 858 858</a>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
