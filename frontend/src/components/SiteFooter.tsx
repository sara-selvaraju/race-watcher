"use client";

import { useEffect, useRef } from "react";

const SEEN_KEY = "race-watcher.welcome-seen";

/** The footer, plus the welcome note shown on a browser's first visit and from "About this site". */
export function SiteFooter() {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let seen = false;
    try {
      seen = localStorage.getItem(SEEN_KEY) === "1";
    } catch {
      // storage blocked: show it, it just won't be remembered
    }
    if (!seen) dialog.current?.showModal();
  }, []);

  function close() {
    try {
      localStorage.setItem(SEEN_KEY, "1");
    } catch {}
    dialog.current?.close();
  }

  return (
    <>
      <footer className="border-t border-line bg-surface text-sm text-ink-3 mt-12">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-5 flex flex-wrap items-center gap-x-6 gap-y-2">
          <span>
            Run by AI and can be wrong. Just for fun, not betting advice.{" "}
            <button
              type="button"
              onClick={() => dialog.current?.showModal()}
              className="font-semibold text-ink-2 underline underline-offset-2"
            >
              About this site
            </button>
          </span>
          <span className="sm:ml-auto">
            Gamble responsibly. Gambling Help{" "}
            <a className="font-semibold text-ink-2 underline underline-offset-2" href="tel:1800858858">
              1800 858 858
            </a>
          </span>
        </div>
      </footer>

      <dialog
        ref={dialog}
        onClose={close}
        aria-labelledby="welcome-title"
        className="w-[calc(100%-2rem)] max-w-md rounded-[10px] border border-line bg-surface p-0 text-ink backdrop:bg-turf-deep/60"
      >
        <div className="h-1.5 bg-silk" />
        <div className="px-6 pt-5 pb-6">
          <h2 id="welcome-title" className="font-display text-3xl font-bold leading-none">
            Race Watcher
          </h2>
          <p className="mt-1 text-ink-2">Follow the Flemington Spring Carnival race by race.</p>
          <p className="mt-4 leading-relaxed">
            This site is run by AI. An AI agent searches the web for bookmaker odds and tips, and an AI
            writes the race notes. It works fast but can get things wrong or be out of date, so check
            anything that matters with a bookmaker.
          </p>
          <p className="mt-3 leading-relaxed">
            This site is just for fun, and not betting advice. Gambling Help:{" "}
            <a className="font-semibold underline underline-offset-2" href="tel:1800858858">
              1800 858 858
            </a>
            .
          </p>
          <button type="button" onClick={close} className="btn btn-primary mt-5" autoFocus>
            Got it
          </button>
        </div>
      </dialog>
    </>
  );
}
