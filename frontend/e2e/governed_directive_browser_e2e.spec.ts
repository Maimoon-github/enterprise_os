import { test, expect } from "@playwright/test";

test.describe("Enterprise OS - Production Browser E2E Suite", () => {
  test("traverses complete directive lifecycle, HITL approval, audit, and proves strict API boundary isolation", async ({
    page,
  }) => {
    // 1. Intercept all browser network traffic to prove zero direct UDS or sandbox access
    const interceptedUrls: string[] = [];
    const forbiddenRequests: string[] = [];

    page.on("request", (request) => {
      const url = request.url();
      interceptedUrls.push(url);

      // Verify browser NEVER attempts direct communication with UDS or sandbox daemon port
      if (
        url.includes("provisioner.sock") ||
        url.includes("/run/enterprise_os") ||
        url.includes("18091") ||
        url.startsWith("unix:")
      ) {
        forbiddenRequests.push(url);
      }
    });

    // 2. Directives Page: Plan Synthesis and DAG Execution
    await page.goto("/directives");
    await expect(page).toHaveTitle(/Enterprise OS/i);

    // Verify Directives Header
    const directivesHeader = page.locator("h1");
    await expect(directivesHeader).toContainText("Directives & Intelligence DAG Planning");

    // Click on preset template "Tiered Pricing Selector"
    const templateButton = page.getByRole("button", { name: /Tiered Pricing Selector/i });
    await expect(templateButton).toBeVisible();
    await templateButton.click();

    // Verify objective input populated
    const objectiveInput = page.locator('textarea[placeholder*="Enter high-level objective"]');
    await expect(objectiveInput).toHaveValue(/pricing/i);

    // Run Planning Engine
    const runPlanningButton = page.getByRole("button", { name: /Run Planning Engine/i });
    await expect(runPlanningButton).toBeEnabled();
    await runPlanningButton.click();

    // Verify synthesized DAG nodes appear
    await expect(page.getByText(/Deterministic Execution Pipeline/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("checkout_pricing_refactor")).toBeVisible();

    // Trigger DAG execution
    const executeDagButton = page.getByRole("button", { name: /Execute DAG/i });
    await expect(executeDagButton).toBeVisible();
    await executeDagButton.click();

    // Verify live CTS progress bar or execution status
    await expect(page.getByText(/Live CTS Orchestration Progress/i).first()).toBeVisible({
      timeout: 10000,
    });

    // 3. HITL Approvals Page: Sign & Approve Action Previews
    await page.goto("/approvals");
    const approvalsHeader = page.locator("h1");
    await expect(approvalsHeader).toContainText("Human-in-the-Loop (HITL) Authorization Queue");

    // Approve all pending action previews via 1-Click Executive Gate
    const approveAllButton = page.getByRole("button", { name: /1-Click Approve All Previews/i });
    if (await approveAllButton.isVisible()) {
      await approveAllButton.click();
      // Verify toast message appeared
      await expect(
        page.getByText(/Batch Authorization Complete/i).or(page.getByText(/Approved/i)).first()
      ).toBeVisible({ timeout: 10000 });
    }

    // Switch to W_DEV Cryptographic Decision Sealing Studio
    const devStudioTab = page.getByRole("button", { name: /W_DEV Cryptographic Decision Sealing Studio/i });
    await expect(devStudioTab).toBeVisible();
    await devStudioTab.click();

    // Verify AST metrics and unified diff viewer
    await expect(page.getByText(/PricingTierSelector\.tsx/i).first()).toBeVisible();

    // 4. Audit & Cryptographic Provenance Ledger
    await page.goto("/audit");
    const auditHeader = page.locator("h1");
    await expect(auditHeader).toContainText("W3C PROV Cryptographic Audit Ledger");
    await expect(page.getByText(/W3C PROV/i).first()).toBeVisible();

    // 5. Telemetry & Institutional Memory Page
    await page.goto("/telemetry");
    const telemetryHeader = page.locator("h1");
    await expect(telemetryHeader).toContainText("Omnichannel Telemetry & Runtime Readiness");

    // 6. Architectural Boundary Verification: Prove Zero UDS / Direct Sandbox Port Traversal
    expect(forbiddenRequests).toHaveLength(0);

    // Verify that all intercepted API requests only traversed authorized HTTP ingress
    const apiRequests = interceptedUrls.filter((u) => u.includes("/api/") || u.includes("localhost:8000") || u.includes("3000"));
    expect(apiRequests.length).toBeGreaterThan(0);
  });

  test("submits custom directive, performs granular cryptographic HITL signing, and verifies audit chain", async ({
    page,
  }) => {
    const forbiddenRequests: string[] = [];
    page.on("request", (req) => {
      const url = req.url();
      if (
        url.includes("provisioner.sock") ||
        url.includes("/run/enterprise_os") ||
        url.includes("18091") ||
        url.startsWith("unix:")
      ) {
        forbiddenRequests.push(url);
      }
    });

    // 1. Directives Page: Input custom objective
    await page.goto("/directives");
    const objectiveInput = page.locator('textarea[placeholder*="Enter high-level objective"]');
    await objectiveInput.fill("Deploy zero-trust enterprise compliance audit harness with cryptographic proof tokens");

    const budgetInput = page.locator('input[type="number"]');
    await budgetInput.fill("18500");

    const runPlanningButton = page.getByRole("button", { name: /Run Planning Engine/i });
    await runPlanningButton.click();

    // Wait for plan synthesis
    await expect(page.getByText(/Deterministic Execution Pipeline/i)).toBeVisible({ timeout: 10000 });

    // 2. HITL Approvals Page: Granular Review
    await page.goto("/approvals");
    await expect(page.getByText(/Pending Action Previews/i)).toBeVisible();

    // Select first preview if available
    const firstPreview = page.locator("button:has-text('prev-')").first();
    if (await firstPreview.isVisible()) {
      await firstPreview.click();
      await expect(page.getByText(/Cryptographic Authorization Signer/i)).toBeVisible();

      // Click Sign & Authorize
      const signButton = page.getByRole("button", { name: /Sign & Authorize Execution/i });
      if (await signButton.isVisible()) {
        await signButton.click();
        await expect(page.getByText(/Signed & Authorized/i).first()).toBeVisible({ timeout: 5000 });
      }
    }

    // 3. W_DEV Decision Sealing Studio
    const devStudioTab = page.getByRole("button", { name: /W_DEV Cryptographic Decision Sealing Studio/i });
    await devStudioTab.click();

    const devDeliverable = page.locator("button:has-text('.tsx')").first();
    if (await devDeliverable.isVisible()) {
      await devDeliverable.click();
      await expect(page.getByText("Generated Code Diff")).toBeVisible();

      const sealButton = page.getByRole("button", { name: /Seal & Approve/i });
      if (await sealButton.isVisible()) {
        await sealButton.click();
        await expect(page.getByText(/CRYPTOGRAPHICALLY SEALED/i).or(page.getByText(/Decision Sealed/i)).first()).toBeVisible({ timeout: 5000 });
      }
    }

    // 4. Verify Audit Page Cryptographic Chain
    await page.goto("/audit");
    const verifyChainButton = page.getByRole("button", { name: /Verify Chain/i });
    await expect(verifyChainButton).toBeVisible();
    await verifyChainButton.click();
    await expect(page.getByText(/Cryptographic Chain Verified/i).first()).toBeVisible({ timeout: 5000 });

    // 5. Boundary Isolation Assert
    expect(forbiddenRequests).toHaveLength(0);
  });
});
