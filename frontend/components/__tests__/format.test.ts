import { describe, expect, it } from "vitest";
import { pct, pnlClass, qty, signed, usd } from "@/lib/format";

describe("format helpers", () => {
  it("formats USD", () => {
    expect(usd(1234.5)).toBe("$1,234.50");
  });

  it("formats signed percentages", () => {
    expect(pct(1.3)).toBe("+1.30%");
    expect(pct(-2)).toBe("-2.00%");
  });

  it("formats signed dollar amounts", () => {
    expect(signed(25)).toBe("+$25.00");
    expect(signed(-10)).toBe("-$10.00");
  });

  it("formats quantities, trimming integers", () => {
    expect(qty(10)).toBe("10");
    expect(qty(1.5)).toBe("1.5000");
  });

  it("maps P&L sign to color classes", () => {
    expect(pnlClass(5)).toBe("text-up");
    expect(pnlClass(-5)).toBe("text-down");
    expect(pnlClass(0)).toBe("text-muted");
  });
});
