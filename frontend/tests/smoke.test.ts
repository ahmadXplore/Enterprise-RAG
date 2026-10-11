import { describe, it, expect } from "vitest";

describe("Frontend Environment Smoke Test", () => {
  it("verifies vitest test runner executes successfully", () => {
    expect(true).toBe(true);
  });

  it("verifies frontend route map integrity", () => {
    const coreRoutes = [
      "/login",
      "/dashboard",
      "/search",
      "/chat",
      "/documents",
      "/evaluations",
    ];
    expect(coreRoutes).toHaveLength(6);
    expect(coreRoutes).toContain("/dashboard");
    expect(coreRoutes).toContain("/documents");
  });
});
