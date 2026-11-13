import { afterEach, describe, expect, test } from "bun:test";

import { CLEANLIST_HANDLERS } from "./actions";
import { CLEANLIST } from "./definition";
import { verifyCleanlistCredentials } from "./verify";
import { validateInputValue } from "../catalog";
import { validateColumnConfig } from "../../grid/columns";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function actionContext(actionKey, inputs, providerState) {
  const action = CLEANLIST.actions.find((candidate) => candidate.key === actionKey);
  if (!action) throw new Error(`Missing test action: ${actionKey}`);
  const config = {
    integrationKey: CLEANLIST.key,
    actionKey: action.key,
    handlerKey: action.handlerKey,
    inputs: {},
    outputs: Object.fromEntries(action.outputs.map((output) => [output.key, output.key])),
    connectionId: "cleanlist-test",
  };
  return {
    action,
    config,
    inputs,
    credentials: { apiKey: "clapi_test" },
    connectionId: "cleanlist-test",
    providerState,
    timeoutMs: 5_000,
  };
}

function handlerFor(actionKey) {
  const action = CLEANLIST.actions.find((candidate) => candidate.key === actionKey);
  if (!action) throw new Error(`Missing test action: ${actionKey}`);
  const handler = CLEANLIST_HANDLERS[action.handlerKey];
  if (!handler) throw new Error(`Missing test handler: ${action.handlerKey}`);
  return handler;
}

describe("Cleanlist integration", () => {
  test("exposes every documented search filter through the guided builder", () => {
    const people = CLEANLIST.actions.find((action) => action.key === "search-people");
    const companies = CLEANLIST.actions.find((action) => action.key === "search-companies");

    expect(people.filterBuilder).toEqual({ minFilters: 1 });
    expect(people.inputs.filter((input) => input.group === "filter" && !input.hidden).map((input) => input.key)).toEqual([
      "titles",
      "seniority",
      "managementLevels",
      "departments",
      "locationCity",
      "locationState",
      "locationCountry",
      "locations",
      "companyNames",
      "companyDomains",
      "companyHeadcount",
      "companyIndustries",
    ]);
    expect(companies.filterBuilder).toEqual({ minFilters: 1 });
    expect(companies.inputs.filter((input) => input.group === "filter" && !input.hidden).map((input) => input.key)).toEqual([
      "industries",
      "employeeCountRanges",
      "locations",
      "names",
      "domains",
    ]);
    expect(companies.inputs.filter((input) => input.group === "advanced").map((input) => input.key)).toEqual([
      "limit",
      "cursor",
    ]);
    expect(people.inputs.filter((input) => input.group === "filter" && !input.hidden).every((input) => input.multiple)).toBe(true);
  });

  test("requires a mapped search filter while accepting named and legacy mappings", () => {
    const action = CLEANLIST.actions.find((candidate) => candidate.key === "search-companies");
    const baseConfig = {
      integrationKey: CLEANLIST.key,
      actionKey: action.key,
      handlerKey: action.handlerKey,
      inputs: {},
      outputs: { companies: "companies" },
      connectionId: "cleanlist-test",
    };
    const columns = [
      { key: "industry", type: "text" },
      { key: "legacyFilters", type: "json" },
    ];

    expect(() => validateColumnConfig("enrichment", baseConfig, columns)).toThrow("Map at least 1 search filter");
    expect(() => validateColumnConfig("enrichment", {
      ...baseConfig,
      inputs: { industries: { source: "column", columnKey: "industry" } },
    }, columns)).not.toThrow();
    expect(() => validateColumnConfig("enrichment", {
      ...baseConfig,
      inputs: { filters: { source: "column", columnKey: "legacyFilters" } },
    }, columns)).not.toThrow();
  });

  test("validates scalar and list-valued filter cells", () => {
    expect(validateInputValue("text", "VP", true)).toBeNull();
    expect(validateInputValue("text", ["VP", "Director"], true)).toBeNull();
    expect(validateInputValue("text", '["VP", "Director"]', true)).toBeNull();
    expect(validateInputValue("text", [], true)).toBe("Expected at least one value");
    expect(validateInputValue("text", ["VP", ""], true)).toContain("Invalid list value");
  });

  test("searches people with explicit filter mappings and maps pagination metadata", async () => {
    let requestBody;
    globalThis.fetch = (async (_input, init) => {
      requestBody = JSON.parse(String(init?.body));
      return Response.json({
        task_id: "cl-task_people",
        results: [{ lead_id: "person-1", full_name: "Alex Morgan" }],
        total: 42,
        cursor: "next-page",
        truncation_warning: null,
        credits_charged: 0,
      });
    });

    const result = await handlerFor("search-people")(
      actionContext("search-people", {
        managementLevels: ["VP", "Director"],
        departments: "Sales, Marketing\nRevenue",
        locationCountry: '["India", "United States"]',
        companyDomains: " acme.com ",
        limit: 100,
      }),
    );

    expect("pending" in result).toBe(false);
    if ("pending" in result) return;
    expect(requestBody).toEqual({
      filters: {
        management_levels: ["VP", "Director"],
        departments: ["Sales", "Marketing", "Revenue"],
        location_country: ["India", "United States"],
        company_domains: ["acme.com"],
      },
      limit: 100,
    });
    expect(result.outcome).toBe("hit");
    expect(result.outputs).toMatchObject({
      resultCount: 1,
      total: 42,
      cursor: "next-page",
      taskId: "cl-task_people",
    });
  });

  test("supports legacy saved filters and lets explicit mappings override them", async () => {
    let requestBody;
    globalThis.fetch = (async (_input, init) => {
      requestBody = JSON.parse(String(init?.body));
      return Response.json({ results: [], total: 0 });
    });

    const result = await handlerFor("search-companies")(
      actionContext("search-companies", {
        filters: JSON.stringify({
          industries: ["Legacy Industry"],
          employee_count_ranges: ["51-200"],
          domains: ["legacy.example"],
        }),
        industries: "Software\nFinancial Services",
        domains: ["example.com", " example.org "],
      }),
    );

    expect("pending" in result).toBe(false);
    expect(requestBody).toEqual({
      filters: {
        industries: ["Software", "Financial Services"],
        employee_count_ranges: ["51-200"],
        domains: ["example.com", "example.org"],
      },
      limit: 25,
    });
  });

  test("keeps legacy-only saved search configurations working", async () => {
    let requestBody;
    globalThis.fetch = (async (_input, init) => {
      requestBody = JSON.parse(String(init?.body));
      return Response.json({ results: [], total: 0 });
    });

    await handlerFor("search-people")(
      actionContext("search-people", {
        filters: { management_levels: ["VP"], departments: ["Sales"] },
      }),
    );

    expect(requestBody).toEqual({
      filters: { management_levels: ["VP"], departments: ["Sales"] },
      limit: 25,
    });
  });

  test("rejects unsupported or empty search filters before calling Cleanlist", async () => {
    let called = false;
    globalThis.fetch = (async () => {
      called = true;
      return Response.json({});
    });

    await expect(
      handlerFor("search-companies")(
        actionContext("search-companies", { filters: { technologies: ["React"] } }),
      ),
    ).rejects.toThrow("Unknown Cleanlist companies filter: technologies");
    await expect(
      handlerFor("search-companies")(
        actionContext("search-companies", { filters: { industries: [] } }),
      ),
    ).rejects.toThrow("non-empty array");
    expect(called).toBe(false);
  });

  test("starts and polls asynchronous person enrichment", async () => {
    const requests = [];
    globalThis.fetch = (async (input, init) => {
      requests.push({
        url: String(input),
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      if (requests.length === 1) {
        return Response.json({ workflow_id: "workflow-1", status: "pending" });
      }
      return Response.json({
        workflow_id: "workflow-1",
        status: "completed",
        credits_charged: 1,
        result: {
          lead_id: "lead-1",
          status: "completed",
          full_name: "Alex Morgan",
          email: "alex@example.com",
          email_status: "valid",
          title: "VP Sales",
          company: "Example",
          provider: "hunter",
        },
      });
    });

    const handler = handlerFor("enrich-person");
    const started = await handler(
      actionContext("enrich-person", {
        leadListId: "list-1",
        linkedinUrl: "https://www.linkedin.com/in/alex-morgan",
      }),
    );
    expect("pending" in started && started.pending).toBe(true);
    const state = started.state;
    expect(state.workflowId).toBe("workflow-1");
    expect(requests[0]?.body).toEqual({
      lead_list_id: "list-1",
      enrichment_type: "partial",
      linkedin_url: "https://www.linkedin.com/in/alex-morgan",
    });

    const completed = await handler(
      actionContext(
        "enrich-person",
        {
          leadListId: "list-1",
          linkedinUrl: "https://www.linkedin.com/in/alex-morgan",
        },
        state,
      ),
    );
    expect("pending" in completed).toBe(false);
    if ("pending" in completed) return;
    expect(requests[1]?.url).toEndWith("/api/v2/enrichment/status/workflow-1");
    expect(completed.outcome).toBe("hit");
    expect(completed.outputs).toMatchObject({
      fullName: "Alex Morgan",
      email: "alex@example.com",
      jobTitle: "VP Sales",
      creditsCharged: 1,
    });
  });

  test("maps synchronous company enrichment", async () => {
    globalThis.fetch = (async () => Response.json({
      company: {
        company_id: "company-1",
        name: "Example",
        domain: "example.com",
        industry: "Software Development",
        industries: ["Software Development"],
        employee_count: 180,
        employee_count_range: "51-200",
        tech_stack: ["React"],
      },
      credits_charged: 1,
    }));

    const result = await handlerFor("enrich-company")(
      actionContext("enrich-company", { domain: "https://www.example.com/about" }),
    );
    expect("pending" in result).toBe(false);
    if ("pending" in result) return;
    expect(result.outcome).toBe("hit");
    expect(result.outputs).toMatchObject({
      companyName: "Example",
      domain: "example.com",
      employeeCount: 180,
      companyId: "company-1",
      creditsCharged: 1,
    });
  });

  test("verifies all scopes needed by the four actions", async () => {
    globalThis.fetch = (async () => Response.json({
      scopes: ["people:read", "companies:read", "enrich:write"],
    }));
    await expect(verifyCleanlistCredentials({ apiKey: "clapi_test" }))
      .rejects.toThrow("enrich:read");

    globalThis.fetch = (async () => Response.json({
      scopes: ["people:read", "companies:read", "enrich:write", "enrich:read"],
    }));
    await expect(verifyCleanlistCredentials({ apiKey: "clapi_test" })).resolves.toBeUndefined();
  });
});
