/** Display formatting helpers. */

export const usd = (n: number): string =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export const pct = (n: number): string => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

export const signed = (n: number): string =>
  `${n >= 0 ? "+" : ""}${usd(n)}`;

export const qty = (n: number): string =>
  Number.isInteger(n) ? String(n) : n.toFixed(4);

export const pnlClass = (n: number): string =>
  n > 0 ? "text-up" : n < 0 ? "text-down" : "text-muted";
