import { describe, it, expect } from "vitest";
import DOMPurify from "isomorphic-dompurify";

describe("Frontend Table HTML Sanitization (DOMPurify)", () => {
  const sanitizeConfig = {
    ALLOWED_TAGS: [
      "table",
      "thead",
      "tbody",
      "tfoot",
      "tr",
      "th",
      "td",
      "caption",
      "colgroup",
      "col",
      "span",
      "div",
      "b",
      "i",
      "strong",
      "em",
      "p",
    ],
    ALLOWED_ATTR: ["class", "id", "style", "colspan", "rowspan", "scope"],
  };

  it("permits safe table markup and attributes", () => {
    const safeTable =
      '<table class="table-auto"><thead><tr><th colspan="2">Revenue</th></tr></thead><tbody><tr><td>Q1</td><td>$100M</td></tr></tbody></table>';
    const cleaned = DOMPurify.sanitize(safeTable, sanitizeConfig);
    expect(cleaned).toContain("<table");
    expect(cleaned).toContain("<thead");
    expect(cleaned).toContain("colspan");
    expect(cleaned).toContain("$100M");
  });

  it("strips script tags and malicious attributes", () => {
    const malicious =
      '<table><tr><td>Product<script>alert("xss")</script></td><td onclick="alert(1)">Price</td></tr></table>';
    const cleaned = DOMPurify.sanitize(malicious, sanitizeConfig);
    expect(cleaned).not.toContain("<script");
    expect(cleaned).not.toContain("alert");
    expect(cleaned).not.toContain("onclick");
    expect(cleaned).toContain("Product");
    expect(cleaned).toContain("Price");
  });

  it("strips iframe and object tags", () => {
    const injection =
      '<div><iframe src="javascript:alert(1)"></iframe><p>Financial Highlights</p></div>';
    const cleaned = DOMPurify.sanitize(injection, sanitizeConfig);
    expect(cleaned).not.toContain("<iframe");
    expect(cleaned).toContain("<p>Financial Highlights</p>");
  });
});
