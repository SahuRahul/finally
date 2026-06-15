import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Header } from "@/components/Header";

describe("Header", () => {
  it("shows total value and cash balance", () => {
    render(<Header totalValue={11925} cashBalance={8075} status="connected" />);
    expect(screen.getByTestId("total-value")).toHaveTextContent("$11,925.00");
    expect(screen.getByTestId("cash-balance")).toHaveTextContent("$8,075.00");
  });

  it("reflects connection status", () => {
    render(<Header totalValue={0} cashBalance={0} status="disconnected" />);
    const dot = screen.getByTestId("connection-status");
    expect(dot).toHaveAttribute("data-status", "disconnected");
    expect(dot).toHaveTextContent("Disconnected");
  });
});
