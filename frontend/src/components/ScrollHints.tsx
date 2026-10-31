"use client";

import { useEffect, useState, type RefObject } from "react";

/** Faint ‹ › at the edges of a sideways-scrolling strip, shown only when there's more that way.
 *  Tapping one scrolls the strip. The parent must be `relative`. */
export function ScrollHints({ target }: { target: RefObject<HTMLElement | null> }) {
  const [more, setMore] = useState({ left: false, right: false });

  useEffect(() => {
    const el = target.current;
    if (!el) return;
    const update = () =>
      setMore({
        left: el.scrollLeft > 4,
        right: el.scrollLeft + el.clientWidth < el.scrollWidth - 4,
      });
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    for (const child of Array.from(el.children)) ro.observe(child);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [target]);

  function scroll(dir: -1 | 1) {
    const el = target.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: reduce ? "auto" : "smooth" });
  }

  return (
    <>
      {more.left && <Arrow side="left" onClick={() => scroll(-1)} />}
      {more.right && <Arrow side="right" onClick={() => scroll(1)} />}
    </>
  );
}

function Arrow({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const left = side === "left";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={left ? "Scroll back" : "Scroll for more"}
      className={`absolute inset-y-0 ${left ? "left-0 justify-start pl-0.5 bg-gradient-to-r" : "right-0 justify-end pr-0.5 bg-gradient-to-l"} z-10 flex w-9 items-center from-[var(--fade)] to-transparent text-ink-3/70 hover:text-ink`}
    >
      <span aria-hidden className="font-display text-3xl leading-none">
        {left ? "‹" : "›"}
      </span>
    </button>
  );
}
