import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/components/ChatPanel";

describe("ChatPanel", () => {
  it("renders the user message and assistant reply with inline actions", async () => {
    const onSend = vi.fn().mockResolvedValue({
      message: "Bought 5 AAPL for you.",
      actions: [
        { type: "trade", status: "executed", ticker: "AAPL", side: "buy", quantity: 5, price: 192.5 },
        { type: "watchlist", status: "executed", ticker: "PYPL", action: "add" },
      ],
    });
    render(<ChatPanel onSend={onSend} />);

    await userEvent.type(screen.getByTestId("chat-input"), "buy 5 aapl");
    await userEvent.click(screen.getByTestId("chat-send-btn"));

    expect(onSend).toHaveBeenCalledWith("buy 5 aapl");
    expect(await screen.findByText("Bought 5 AAPL for you.")).toBeInTheDocument();

    const actions = screen.getAllByTestId("chat-action");
    expect(actions[0]).toHaveTextContent("Bought 5 AAPL @ $192.50");
    expect(actions[1]).toHaveTextContent("Added PYPL");
  });

  it("renders a failed trade action with its error", async () => {
    const onSend = vi.fn().mockResolvedValue({
      message: "That trade could not be filled.",
      actions: [
        {
          type: "trade",
          status: "error",
          ticker: "AAPL",
          side: "buy",
          quantity: 1000,
          error: "Insufficient cash",
        },
      ],
    });
    render(<ChatPanel onSend={onSend} />);
    await userEvent.type(screen.getByTestId("chat-input"), "buy 1000 aapl");
    await userEvent.click(screen.getByTestId("chat-send-btn"));
    expect(await screen.findByTestId("chat-action")).toHaveTextContent(
      "BUY 1000 AAPL failed: Insufficient cash",
    );
  });

  it("shows an error reply when the request fails", async () => {
    const onSend = vi.fn().mockRejectedValue(new Error("LLM unavailable"));
    render(<ChatPanel onSend={onSend} />);
    await userEvent.type(screen.getByTestId("chat-input"), "hello");
    await userEvent.click(screen.getByTestId("chat-send-btn"));
    expect(await screen.findByText("LLM unavailable")).toBeInTheDocument();
  });
});
