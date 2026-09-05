import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { Navbar } from "@/components/layout/Navbar";
import * as apiClient from "@/lib/api-client";

function TestAuthConsumer() {
  const { user, activeMerchant, merchants, isLoading, error } = useAuth();
  return (
    <div>
      <span data-testid="auth-loading">{isLoading ? "loading" : "idle"}</span>
      <span data-testid="auth-user">{user ? user.email : "anonymous"}</span>
      <span data-testid="auth-merchant">{activeMerchant ? activeMerchant.name : "none"}</span>
      <span data-testid="auth-error">{error || "none"}</span>
      <span data-testid="auth-merchants-count">{merchants.length}</span>
    </div>
  );
}

describe("AuthContext & Navbar Integration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders anonymous/unauthenticated state when no token is present", async () => {
    render(
      <AuthProvider>
        <TestAuthConsumer />
        <Navbar />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("idle");
    });

    expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("auth-merchant")).toHaveTextContent("none");
    expect(screen.getByText("Phase 3 RBAC Enforced")).toBeInTheDocument();
  });

  it("populates user and active merchant when authentication succeeds", async () => {
    process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN = "valid.jwt.token";

    vi.spyOn(apiClient, "fetchCurrentUser").mockResolvedValue({
      id: "usr_alice123",
      email: "alice@acme.com",
      email_verified: true,
      created_at: new Date().toISOString(),
    });

    vi.spyOn(apiClient, "fetchUserMerchants").mockResolvedValue([
      {
        id: "merch_acme",
        name: "Acme Corp",
        slug: "acme-corp",
        role: "OWNER",
        status: "ACTIVE",
      },
      {
        id: "merch_beta",
        name: "Beta LLC",
        slug: "beta-llc",
        role: "OPERATOR",
        status: "ACTIVE",
      },
    ]);

    render(
      <AuthProvider>
        <TestAuthConsumer />
        <Navbar />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-user")).toHaveTextContent("alice@acme.com");
    });

    expect(screen.getByTestId("auth-merchant")).toHaveTextContent("Acme Corp");
    expect(screen.getByTestId("auth-merchants-count")).toHaveTextContent("2");
    expect(screen.getAllByText("alice@acme.com").length).toBeGreaterThanOrEqual(1);

    // Select merchant dropdown
    const select = screen.getByLabelText("Active Merchant");
    expect(select).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "merch_beta" } });

    await waitFor(() => {
      expect(screen.getByTestId("auth-merchant")).toHaveTextContent("Beta LLC");
    });

    // Test sign out
    const signOutBtn = screen.getByTitle("Sign Out");
    fireEvent.click(signOutBtn);

    await waitFor(() => {
      expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");
      expect(screen.getByTestId("auth-merchant")).toHaveTextContent("none");
    });

    delete process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN;
  });
});
