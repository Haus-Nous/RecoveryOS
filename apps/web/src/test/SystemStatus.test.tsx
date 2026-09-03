import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SystemStatus } from "@/components/system/SystemStatus";
import * as apiClient from "@/lib/api-client";

describe("SystemStatus Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading/checking state initially", () => {
    vi.spyOn(apiClient, "checkFullSystemStatus").mockImplementation(
      () => new Promise(() => {}) // never resolves
    );

    render(<SystemStatus initialAutoPoll={false} />);
    expect(screen.getByTestId("status-badge")).toHaveTextContent("CHECKING");
  });

  it("renders healthy state when API and dependencies are operational", async () => {
    vi.spyOn(apiClient, "checkFullSystemStatus").mockResolvedValue({
      health: { status: "ok", service: "recoveryos-api" },
      readiness: {
        status: "ready",
        service: "recoveryos-api",
        dependencies: { postgres: "connected", redis: "connected" },
        errors: [],
      },
      latencyMs: 15,
    });

    render(<SystemStatus initialAutoPoll={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("SYSTEM OPERATIONAL");
    });

    expect(screen.getByTestId("postgres-card")).toHaveTextContent("CONNECTED");
    expect(screen.getByTestId("redis-card")).toHaveTextContent("CONNECTED");
    expect(screen.getByText(/Roundtrip Latency: 15ms/i)).toBeInTheDocument();
  });

  it("renders degraded/unavailable state when dependency fails", async () => {
    vi.spyOn(apiClient, "checkFullSystemStatus").mockResolvedValue({
      health: { status: "ok", service: "recoveryos-api" },
      readiness: {
        status: "not_ready",
        service: "recoveryos-api",
        dependencies: { postgres: "connected", redis: "disconnected" },
        errors: ["Redis: Connection timeout"],
      },
      latencyMs: 25,
    });

    render(<SystemStatus initialAutoPoll={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("SERVICE DEGRADED");
    });

    expect(screen.getByTestId("redis-card")).toHaveTextContent("DISCONNECTED");
    expect(screen.getByTestId("error-banner")).toHaveTextContent("Redis: Connection timeout");
  });

  it("renders network error and handles retry to recover to healthy state", async () => {
    const checkSpy = vi
      .spyOn(apiClient, "checkFullSystemStatus")
      .mockRejectedValueOnce(new Error("Network connection refused"))
      .mockResolvedValueOnce({
        health: { status: "ok", service: "recoveryos-api" },
        readiness: {
          status: "ready",
          service: "recoveryos-api",
          dependencies: { postgres: "connected", redis: "connected" },
          errors: [],
        },
        latencyMs: 8,
      });

    render(<SystemStatus initialAutoPoll={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("SERVICE DEGRADED");
    });
    expect(screen.getByTestId("error-banner")).toHaveTextContent("Network connection refused");

    // Click retry button
    const retryButton = screen.getByTestId("refresh-button");
    expect(retryButton).toHaveTextContent("Retry Connection");
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("SYSTEM OPERATIONAL");
    });
    expect(checkSpy).toHaveBeenCalledTimes(2);
  });
});
