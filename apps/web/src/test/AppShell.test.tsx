import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Home from "@/app/page";
import * as apiClient from "@/lib/api-client";

describe("RecoveryOS Frontend App Shell", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "checkFullSystemStatus").mockResolvedValue({
      health: { status: "ok", service: "recoveryos-api" },
      readiness: {
        status: "ready",
        service: "recoveryos-api",
        dependencies: { postgres: "connected", redis: "connected" },
        errors: [],
      },
      latencyMs: 12,
    });
  });

  it("renders the application title and control plane subtitle", async () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1, name: "RecoveryOS" })).toBeInTheDocument();
    expect(
      screen.getByText("Payment Reliability & Revenue Recovery Control Plane")
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("SYSTEM OPERATIONAL");
    });
  });

  it("renders the non-negotiable architectural invariant", async () => {
    render(<Home />);
    expect(screen.getByText("AI Proposes")).toBeInTheDocument();
    expect(screen.getByText("Policy Authorizes")).toBeInTheDocument();
    expect(screen.getByText("Infra Executes")).toBeInTheDocument();
    expect(screen.getByText("Ledger Verifies")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("SYSTEM OPERATIONAL");
    });
  });

  it("renders all navigation items and displays honest placeholder states on click", async () => {
    render(<Home />);

    // Click on Revenue at Risk tab
    const revenueTab = screen.getByRole("button", { name: /Revenue at Risk/i });
    fireEvent.click(revenueTab);
    expect(screen.getByRole("heading", { level: 2, name: /Revenue at Risk/i })).toBeInTheDocument();
    expect(screen.getByText(/Honest State: No recovery data yet/i)).toBeInTheDocument();

    // Click on Recovery Cases tab
    const casesTab = screen.getByRole("button", { name: /Recovery Cases/i });
    fireEvent.click(casesTab);
    expect(screen.getByRole("heading", { level: 2, name: /Recovery Cases/i })).toBeInTheDocument();

    // Click on Payment Journeys tab
    const journeysTab = screen.getByRole("button", { name: /Payment Journeys/i });
    fireEvent.click(journeysTab);
    expect(screen.getByText(/Honest State: Provider integration not configured/i)).toBeInTheDocument();

    // Return to Overview tab
    const overviewTab = screen.getByRole("button", { name: /Overview/i });
    fireEvent.click(overviewTab);
    expect(screen.getByRole("heading", { level: 1, name: "RecoveryOS" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("SYSTEM OPERATIONAL");
    });
  });
});
