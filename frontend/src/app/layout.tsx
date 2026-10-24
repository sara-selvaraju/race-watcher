import "@/styles/globals.css";
import type { Metadata } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import { QueryProvider } from "@/components/QueryProvider";

const display = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const sans = Barlow({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Race Watcher",
  description: "Personal race-day dashboard. Heuristic ratings, not financial advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body className="min-h-screen">
        <QueryProvider>{children}</QueryProvider>
        <footer className="border-t border-line bg-surface text-sm text-ink-3 mt-12">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 py-5 flex flex-wrap items-center gap-x-6 gap-y-2">
            <span>Ratings are a heuristic, not financial advice. Personal use only.</span>
            <span className="sm:ml-auto">
              Gamble responsibly. Gambling Help{" "}
              <a className="font-semibold text-ink-2 underline underline-offset-2" href="tel:1800858858">
                1800 858 858
              </a>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
