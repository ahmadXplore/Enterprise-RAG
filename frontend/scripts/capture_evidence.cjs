const { chromium } = require("playwright");
const path = require("path");

async function main() {
  console.log("Launching browser for evidence modal capture...");
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
  const page = await context.newPage();

  // Login
  await page.goto("http://localhost:3000/login", { waitUntil: "domcontentloaded" });
  await page.fill('input[type="email"]', "Ahmad@gmail.com");
  await page.fill('input[type="password"]', "Admin123!");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 15000 });

  // Inject session with citation into localStorage
  console.log("Setting localStorage session...");
  await page.evaluate(() => {
    const sampleSession = [
      {
        id: "session-evidence-demo",
        title: "Continual Learning in Recurrent Neural Networks",
        createdAt: Date.now() - 3600000,
        updatedAt: Date.now(),
        messages: [
          {
            id: "msg-user-1",
            role: "user",
            content: "What are the primary empirical benchmarks and architectural trade-offs for Continual Learning in Recurrent Neural Networks?",
          },
          {
            id: "msg-assistant-1",
            role: "assistant",
            content: "Continual learning in recurrent neural networks requires balancing plasticity and stability across sequential memory benchmarks [1].",
            grounded: true,
            citations: [
              {
                chunk_id: "chunk-768e2df8-001",
                document_id: "768e2df8-ddb3-4740-8888-0f8513fab7e8",
                document_title: "[AI ML] 2103 07492v4 · Continual Learning for Recurrent Neural Networks an Empirical Benchmark",
                citation_label: "Section 3.2 · Parameter Regularization & Stability",
                page: 4,
                evidence_text: "In this benchmark, we systematically assess catastrophic forgetting across five sequential memory tasks. Vanilla recurrent models suffer sharp performance drops (>65% accuracy degradation on Task 1 after Task 3 introduction), whereas regularized synaptic architectures retain 91.8% baseline retention.",
              },
            ],
            steps: [],
            durationSeconds: 1.84,
          },
        ],
      },
    ];
    localStorage.setItem("enterprise_rag_chat_memory_v1", JSON.stringify(sampleSession));
  });

  // Navigate to chat
  console.log("Navigating to /chat...");
  await page.goto("http://localhost:3000/chat", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  // Click citation card
  console.log("Clicking citation card...");
  const card = page.locator("button:has-text('Parameter Regularization')").first();
  await card.waitFor({ state: "visible", timeout: 10000 });
  await card.click();
  await page.waitForTimeout(3000);

  console.log("Capturing Evidence Viewer modal...");
  await page.screenshot({
    path: path.resolve(__dirname, "../../docs/screenshots/evidence_viewer.png"),
    fullPage: false,
  });
  console.log("Captured evidence_viewer.png successfully!");

  await browser.close();
}

main().catch(err => { console.error(err); process.exit(1); });
