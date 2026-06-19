import "@/styles/globals.css";
import type { Metadata } from "next";
import { QueryProvider } from "@/components/QueryProvider";

export const metadata: Metadata = {
  title: "race-watcher · Flemington 2026-06-20",
  description: "Personal race-day dashboard. Heuristic ratings, not financial advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <QueryProvider>{children}</QueryProvider>
        <footer className="border-t border-zinc-800 bg-zinc-950 text-xs text-zinc-500 mt-8">
          <div className="mx-auto max-w-6xl px-4 py-4">
            For personal use only. Heuristic ratings, not financial advice.
            Gambling Help <a className="underline" href="tel:1800858858">1800 858 858</a>.
          </div>
        </footer>
      </body>
    </html>
  );
}
