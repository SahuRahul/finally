import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PriceCell } from "@/components/PriceCell";

describe("PriceCell", () => {
  it("renders -- when price is null", () => {
    render(<PriceCell price={null} />);
    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("renders a formatted price", () => {
    render(<PriceCell price={192.5} />);
    expect(screen.getByText("$192.50")).toBeInTheDocument();
  });

  it("applies a green flash class on an uptick", () => {
    const { rerender, container } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={101} />);
    expect(container.querySelector(".flash-up")).not.toBeNull();
  });

  it("applies a red flash class on a downtick", () => {
    const { rerender, container } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={99} />);
    expect(container.querySelector(".flash-down")).not.toBeNull();
  });
});
