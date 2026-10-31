import "@/styles/globals.css";
import type { Metadata } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import { QueryProvider } from "@/components/QueryProvider";
import { SiteFooter } from "@/components/SiteFooter";

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
  description:
    "Follow the Flemington Spring Carnival race by race: odds, market moves, tips and race notes gathered and written by AI. Just for fun, not betting advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body className="min-h-screen">
        <QueryProvider>{children}</QueryProvider>
        <SiteFooter />
      </body>
    </html>
  );
}
