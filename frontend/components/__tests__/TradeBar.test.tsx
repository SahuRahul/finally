import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TradeBar } from "@/components/TradeBar";

describe("TradeBar", () => {
  it("submits a buy with the entered ticker and quantity", async () => {
    const onTrade = vi.fn().mockResolvedValue(undefined);
    render(<TradeBar ticker={null} onTrade={onTrade} />);
    await userEvent.type(screen.getByTestId("trade-ticker"), "aapl");
    await userEvent.type(screen.getByTestId("trade-quantity"), "5");
    await userEvent.click(screen.getByTestId("trade-buy-btn"));
    expect(onTrade).toHaveBeenCalledWith("AAPL", 5, "buy");
  });

  it("submits a sell", async () => {
    const onTrade = vi.fn().mockResolvedValue(undefined);
    render(<TradeBar ticker="MSFT" onTrade={onTrade} />);
    await userEvent.type(screen.getByTestId("trade-quantity"), "2");
    await userEvent.click(screen.getByTestId("trade-sell-btn"));
    expect(onTrade).toHaveBeenCalledWith("MSFT", 2, "sell");
  });

  it("rejects an invalid quantity", async () => {
    const onTrade = vi.fn();
    render(<TradeBar ticker="AAPL" onTrade={onTrade} />);
    await userEvent.click(screen.getByTestId("trade-buy-btn"));
    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByText(/positive quantity/i)).toBeInTheDocument();
  });

  it("surfaces a trade error", async () => {
    const onTrade = vi.fn().mockRejectedValue(new Error("Insufficient cash"));
    render(<TradeBar ticker="AAPL" onTrade={onTrade} />);
    await userEvent.type(screen.getByTestId("trade-quantity"), "1000");
    await userEvent.click(screen.getByTestId("trade-buy-btn"));
    expect(await screen.findByText("Insufficient cash")).toBeInTheDocument();
  });
});
