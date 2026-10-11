import { describe, it, expect, beforeEach } from "vitest";
import { setToken, getToken, clearToken, setUser, getUser, isAdmin, isAnalyst } from "../lib/auth";
import { loginSchema } from "../lib/validators";

describe("Frontend Auth Helpers", () => {
  beforeEach(() => {
    // Reset localstorage mock
    clearToken();
  });

  it("stores and retrieves access tokens", () => {
    setToken("mock_jwt_token_123");
    expect(getToken()).toBe("mock_jwt_token_123");
  });

  it("clears stored token and user data on logout", () => {
    setToken("mock_token");
    setUser({
      id: "u1",
      email: "test@example.com",
      full_name: "Test User",
      roles: ["viewer"],
    });

    clearToken();
    expect(getToken()).toBeNull();
    expect(getUser()).toBeNull();
  });

  it("evaluates admin and analyst role permissions correctly", () => {
    setUser({
      id: "u2",
      email: "admin@enterprise.com",
      full_name: "Admin User",
      roles: ["admin"],
    });

    expect(isAdmin()).toBe(true);
    expect(isAnalyst()).toBe(true);

    setUser({
      id: "u3",
      email: "analyst@enterprise.com",
      full_name: "Analyst User",
      roles: ["analyst"],
    });

    expect(isAdmin()).toBe(false);
    expect(isAnalyst()).toBe(true);

    setUser({
      id: "u4",
      email: "viewer@enterprise.com",
      full_name: "Viewer User",
      roles: ["viewer"],
    });

    expect(isAdmin()).toBe(false);
    expect(isAnalyst()).toBe(false);
  });
});

describe("Frontend Form Validation", () => {
  it("validates login schema constraints", () => {
    const valid = loginSchema.safeParse({
      email: "analyst@company.com",
      password: "securePassword123",
    });
    expect(valid.success).toBe(true);

    const invalidEmail = loginSchema.safeParse({
      email: "not-an-email",
      password: "pass",
    });
    expect(invalidEmail.success).toBe(false);

    const emptyPass = loginSchema.safeParse({
      email: "user@corp.com",
      password: "",
    });
    expect(emptyPass.success).toBe(false);
  });
});
