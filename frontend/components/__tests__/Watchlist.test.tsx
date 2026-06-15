import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Watchlist } from "@/components/Watchlist";
import type { PriceMap, WatchlistItem } from "@/lib/types";

const items: WatchlistItem[] = [
  {
    ticker: "AAPL",
    price: 190,
    previous_price: 189,
    change: 1,
    change_percent: 0.53,
    direction: "up",
  },
];

const prices: PriceMap = {
  AAPL: {
    ticker: "AAPL",
    price: 192.5,
    previous_price: 190,
    timestamp: 0,
    change: 2.5,
    change_percent: 1.32,
    direction: "up",
  },
};

describe("Watchlist", () => {
  it("renders rows and prefers live prices", () => {
    render(
      <Watchlist
        items={items}
        prices={prices}
        history={{}}
        selected={null}
        onSelect={() => {}}
        onAdd={() => {}}
        onRemove={() => {}}
      />,
    );
    const row = screen.getByTestId("watchlist-row-AAPL");
    expect(row).toHaveTextContent("AAPL");
    expect(row).toHaveTextContent("$192.50");
    expect(within(row).getByTestId("price")).toHaveTextContent("$192.50");
  });

  it("selects a ticker on row click", async () => {
    const onSelect = vi.fn();
    render(
      <Watchlist
        items={items}
        prices={prices}
        history={{}}
        selected={null}
        onSelect={onSelect}
        onAdd={() => {}}
        onRemove={() => {}}
      />,
    );
    await userEvent.click(screen.getByTestId("watchlist-row-AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("adds an uppercased ticker", async () => {
    const onAdd = vi.fn();
    render(
      <Watchlist
        items={items}
        prices={prices}
        history={{}}
        selected={null}
        onSelect={() => {}}
        onAdd={onAdd}
        onRemove={() => {}}
      />,
    );
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "pypl");
    await userEvent.click(screen.getByTestId("watchlist-add-btn"));
    expect(onAdd).toHaveBeenCalledWith("PYPL");
  });

  it("removes a ticker without selecting it", async () => {
    const onRemove = vi.fn();
    const onSelect = vi.fn();
    render(
      <Watchlist
        items={items}
        prices={prices}
        history={{}}
        selected={null}
        onSelect={onSelect}
        onAdd={() => {}}
        onRemove={onRemove}
      />,
    );
    await userEvent.click(screen.getByTestId("watchlist-remove-AAPL"));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
    expect(onSelect).not.toHaveBeenCalled();
  });
});
