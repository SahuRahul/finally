"use client";

import { useEffect, useRef, useState } from "react";
import { usd } from "@/lib/format";

/**
 * Renders a price and briefly applies a green/red flash class whenever the
 * value changes. The class is cleared after the CSS animation (~500ms).
 */
export function PriceCell({ price, testId }: { price: number | null; testId?: string }) {
  const prev = useRef<number | null>(price);
  const [flash, setFlash] = useState<"flash-up" | "flash-down" | "">("");

  useEffect(() => {
    if (price === null || prev.current === null || price === prev.current) {
      prev.current = price;
      return;
    }
    setFlash(price > prev.current ? "flash-up" : "flash-down");
    prev.current = price;
    const t = setTimeout(() => setFlash(""), 500);
    return () => clearTimeout(t);
  }, [price]);

  return (
    <span
      data-testid={testId}
      className={`inline-block rounded px-1 font-mono tabular-nums ${flash}`}
    >
      {price === null ? "--" : usd(price)}
    </span>
  );
}
