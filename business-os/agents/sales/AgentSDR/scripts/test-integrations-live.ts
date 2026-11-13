// Runs in ORGANIZATION_ID, or the initial organization when it is unset.
import { runScriptInOrganization } from "./lib/organization";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import { INTEGRATIONS, validateInputValue } from "../src/lib/integrations/catalog";
import type { CellResult, EnrichmentConfig, PendingCellResult } from "../src/lib/grid/types";
import type { IntegrationActionDefinition, IntegrationDefinition } from "../src/lib/integrations/types";

type TestPerson = {
  firstName: string;
  lastName: string;
  fullName: string;
  email: string;
  domain: string;
  companyName: string;
  linkedinUrl: string;
  companyLinkedinUrl: string;
  jobTitle: string;
  startDate: string;
};

// The person every live provider call looks up. Live tests need a real,
// findable public profile you are allowed to look up, so it is supplied by the
// operator, never committed: `--person <path>` or LIVE_TEST_PERSON=<path> to a
// JSON file shaped like scripts/examples/live-test-person.example.json.
function loadTestPerson(): TestPerson {
  const flagIndex = process.argv.indexOf("--person");
  const path = (flagIndex >= 0 ? process.argv[flagIndex + 1] : undefined) || process.env.LIVE_TEST_PERSON;
  if (!path) {
    console.error(
      "No test person given. Pass --person <path> or set LIVE_TEST_PERSON=<path> to a JSON file.\n" +
        "Copy scripts/examples/live-test-person.example.json outside the repo and fill in a real, " +
        "publicly findable person you are allowed to look up.",
    );
    process.exit(1);
  }
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(readFileSync(resolve(path), "utf8"));
  } catch (error) {
    console.error(`Could not read test person file ${path}: ${error instanceof Error ? error.message : error}`);
    process.exit(1);
  }
  const keys: (keyof TestPerson)[] = [
    "firstName", "lastName", "fullName", "email", "domain", "companyName",
    "linkedinUrl", "companyLinkedinUrl", "jobTitle", "startDate",
  ];
  const missing = keys.filter((key) => typeof parsed[key] !== "string" || !parsed[key]);
  if (missing.length > 0) {
    console.error(`Test person file ${path} is missing string field(s): ${missing.join(", ")}`);
    process.exit(1);
  }
  return Object.fromEntries(keys.map((key) => [key, parsed[key]])) as TestPerson;
}

const TEST_DATA: TestPerson = loadTestPerson();

type Status = "passed" | "failed" | "blocked";
type ActionResult = {
  integrationKey: string;
  integrationName: string;
  actionKey: string;
  actionName: string;
  handlerKey: string;
  docsUrl: string;
  status: Status;
  startedAt: string;
  finishedAt: string;
  durationMs: number;
  connection?: { id: string; name: string };
  inputs: Record<string, unknown>;
  inputContract: { valid: boolean; issues: string[] };
  outputContract?: { valid: boolean; issues: string[] };
  attempts?: number;
  outcome?: string;
  value?: unknown;
  outputs?: Record<string, unknown>;
  request?: unknown;
  response?: unknown;
  error?: { name: string; message: string };
  blockedReason?: string;
  sideEffect?: string;
};

type Report = {
  schemaVersion: 1;
  generatedAt: string;
  completedAt?: string;
  testData: typeof TEST_DATA;
  safety: {
    credentialValuesRecorded: false;
    notes: string[];
  };
  summary: {
    totalIntegrations: number;
    totalActions: number;
    passed: number;
    failed: number;
    blocked: number;
  };
  connections: Array<{
    integrationKey: string;
    connectionId?: string;
    connectionName?: string;
    available: boolean;
    reason?: string;
  }>;
  prerequisiteCalls: Array<Record<string, unknown>>;
  actions: ActionResult[];
};

type RuntimeArtifacts = {
  apolloContactId?: string;
  apolloOrganizationId?: string;
  apolloAccountId?: string;
  apolloSequenceId?: string;
  apolloEmailAccountId?: string;
  apolloUserId?: string;
};

const reportArgIndex = process.argv.indexOf("--report");
const reportPath = resolve(
  reportArgIndex >= 0 && process.argv[reportArgIndex + 1]
    ? process.argv[reportArgIndex + 1]
    : "reports/integrations/live-test-latest.json",
);
const integrationArgIndex = process.argv.indexOf("--integration");
const integrationFilter = integrationArgIndex >= 0 ? process.argv[integrationArgIndex + 1] : undefined;
const actionArgIndex = process.argv.indexOf("--action");
const actionFilter = actionArgIndex >= 0 ? process.argv[actionArgIndex + 1] : undefined;
const mergeArgIndex = process.argv.indexOf("--merge-into");
const mergePath = mergeArgIndex >= 0 && process.argv[mergeArgIndex + 1]
  ? resolve(process.argv[mergeArgIndex + 1])
  : undefined;

function isPending(value: CellResult | PendingCellResult): value is PendingCellResult {
  return "pending" in value && value.pending === true;
}

function sleep(ms: number) {
  return new Promise<void>((resolveSleep) => setTimeout(resolveSleep, ms));
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function records(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(record) : [];
}

function sanitize(value: unknown, seen = new WeakSet<object>()): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") return value.length > 20_000 ? `${value.slice(0, 20_000)}…` : value;
  if (typeof value !== "object") return value;
  if (seen.has(value)) return "[circular]";
  seen.add(value);
  const sanitized = Array.isArray(value)
    ? value.slice(0, 100).map((item) => sanitize(item, seen))
    : Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => [
      key,
      /api.?key|authorization|access.?token|refresh.?token|client.?secret|password|credential/i.test(key)
        ? "[redacted]"
        : sanitize(item, seen),
    ]));
  seen.delete(value);
  return sanitized;
}

function summarize(report: Report) {
  report.summary.passed = report.actions.filter((item) => item.status === "passed").length;
  report.summary.failed = report.actions.filter((item) => item.status === "failed").length;
  report.summary.blocked = report.actions.filter((item) => item.status === "blocked").length;
}

async function save(report: Report) {
  summarize(report);
  report.generatedAt = new Date().toISOString();
  await mkdir(dirname(reportPath), { recursive: true });
  await writeFile(reportPath, `${JSON.stringify(sanitize(report), null, 2)}\n`, "utf8");
}

function baseInputs(action: IntegrationActionDefinition): Record<string, unknown> {
  const values: Record<string, unknown> = {
    email: TEST_DATA.email,
    firstName: TEST_DATA.firstName,
    lastName: TEST_DATA.lastName,
    fullName: TEST_DATA.fullName,
    linkedinUrl: TEST_DATA.linkedinUrl,
    profileUrl: TEST_DATA.linkedinUrl,
    domain: TEST_DATA.domain,
    companyDomain: TEST_DATA.domain,
    company: TEST_DATA.domain,
    companyName: TEST_DATA.companyName,
    jobTitle: TEST_DATA.jobTitle,
    startDate: TEST_DATA.startDate,
    postedWithinDays: 30,
    page: 1,
    searchType: "prospects",
    filters: {
      prospect: { first_name: [TEST_DATA.firstName], last_name: [TEST_DATA.lastName] },
      company: { name: { include: [TEST_DATA.companyName] } },
    },
    ipAddress: "8.8.8.8",
    query: TEST_DATA.email,
    mode: "stop",
  };
  return Object.fromEntries(action.inputs.flatMap((input) =>
    values[input.key] === undefined ? [] : [[input.key, values[input.key]]],
  ));
}

function resolveInputs(action: IntegrationActionDefinition, artifacts: RuntimeArtifacts) {
  const inputs = baseInputs(action);
  const requiredArtifact: Record<string, keyof RuntimeArtifacts> = {
    userId: "apolloUserId",
    contactId: "apolloContactId",
    organizationId: "apolloOrganizationId",
    accountId: "apolloAccountId",
    sequenceId: "apolloSequenceId",
    emailAccountId: "apolloEmailAccountId",
  };
  for (const input of action.inputs) {
    const artifactKey = requiredArtifact[input.key];
    if (artifactKey && artifacts[artifactKey]) inputs[input.key] = artifacts[artifactKey];
  }
  if (action.handlerKey === "apollo.updateContact") {
    delete inputs.firstName;
    delete inputs.lastName;
    delete inputs.jobTitle;
    delete inputs.companyName;
    inputs.email = TEST_DATA.email;
  }
  if (action.handlerKey === "icypeas.enrichCompany") {
    inputs.profileUrl = TEST_DATA.companyLinkedinUrl;
  }
  if (action.handlerKey === "apollo.findEmailAccountsForUser" && artifacts.apolloUserId) {
    inputs.userId = artifacts.apolloUserId;
  }
  if (action.handlerKey === "apollo.addContactToSequence") {
    inputs.sequenceId = artifacts.apolloSequenceId;
    inputs.contactId = artifacts.apolloContactId;
    inputs.emailAccountId = artifacts.apolloEmailAccountId;
  }
  if (action.handlerKey === "apollo.updateContactStatusInSequence") {
    inputs.sequenceId = artifacts.apolloSequenceId;
    inputs.contactId = artifacts.apolloContactId;
    inputs.mode = "stop";
  }
  return inputs;
}

function inputIssues(action: IntegrationActionDefinition, inputs: Record<string, unknown>) {
  const issues: string[] = [];
  for (const input of action.inputs) {
    const value = inputs[input.key];
    if (!input.required && (value === undefined || value === null || value === "")) continue;
    const issue = validateInputValue(input.valueType, value, input.multiple);
    if (issue) issues.push(`${input.key}: ${issue}`);
  }
  return issues;
}

function outputTypeIssue(type: string, value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (type === "text" || type === "select" || type === "image") return typeof value === "string" ? null : "expected string";
  if (type === "number" || type === "currency") return typeof value === "number" && Number.isFinite(value) ? null : "expected finite number";
  if (type === "boolean") return typeof value === "boolean" ? null : "expected boolean";
  if (type === "email") return typeof value === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? null : "expected email";
  if (type === "url") {
    if (typeof value !== "string") return "expected URL string";
    try {
      const parsed = new URL(value.includes("://") ? value : `https://${value}`);
      return parsed.hostname.includes(".") ? null : "expected URL";
    } catch {
      return "expected URL";
    }
  }
  if (type === "date") return Number.isNaN(Date.parse(String(value))) ? "expected date" : null;
  if (type === "json" || type === "multiselect") return typeof value === "object" ? null : "expected object or array";
  return null;
}

function outputIssues(action: IntegrationActionDefinition, result: CellResult) {
  const issues: string[] = [];
  if (!result || typeof result !== "object") return ["handler did not return an object"];
  if (!new Set(["hit", "miss", "error", "skipped"]).has(result.outcome)) issues.push("invalid outcome");
  if (typeof result.costCents !== "number" || !Number.isFinite(result.costCents)) issues.push("invalid costCents");
  if (result.provider === undefined || typeof result.provider !== "string") issues.push("missing provider");
  if (result.latencyMs === undefined || typeof result.latencyMs !== "number") issues.push("missing latencyMs");
  if (!result.request || typeof result.request !== "object") issues.push("missing request audit metadata");
  const outputs = record(result.outputs);
  const declared = new Set(action.outputs.map((output) => output.key));
  for (const key of Object.keys(outputs)) if (!declared.has(key)) issues.push(`undeclared output: ${key}`);
  for (const output of action.outputs) {
    if (!(output.key in outputs)) issues.push(`missing output key: ${output.key}`);
    const issue = outputTypeIssue(output.columnType, outputs[output.key]);
    if (issue) issues.push(`${output.key}: ${issue}`);
  }
  const hasMeaningfulOutput = Object.values(outputs).some((value) =>
    value !== null
    && value !== undefined
    && value !== ""
    && value !== false
    && value !== 0
    && (!Array.isArray(value) || value.length > 0),
  );
  if (result.outcome === "hit" && !hasMeaningfulOutput) {
    issues.push("outcome is hit but all declared outputs are empty");
  }
  return issues;
}

function extractApolloArtifacts(action: IntegrationActionDefinition, result: CellResult, artifacts: RuntimeArtifacts) {
  const outputs = record(result.outputs);
  const response = record(result.response);
  if (typeof outputs.contactId === "string") artifacts.apolloContactId = outputs.contactId;
  if (typeof outputs.userId === "string") artifacts.apolloUserId = outputs.userId;
  if (typeof outputs.emailAccountId === "string") artifacts.apolloEmailAccountId = outputs.emailAccountId;
  const organization = record(response.organization);
  if (typeof organization.id === "string") artifacts.apolloOrganizationId = organization.id;
  const personOrganization = record(record(response.person).organization);
  if (typeof personOrganization.id === "string") artifacts.apolloOrganizationId = personOrganization.id;
  const contacts = records(response.contacts);
  const firstContact = contacts[0] ?? {};
  if (!artifacts.apolloContactId && typeof firstContact.id === "string") artifacts.apolloContactId = firstContact.id;
  if (!artifacts.apolloOrganizationId && typeof firstContact.organization_id === "string") {
    artifacts.apolloOrganizationId = firstContact.organization_id;
  }
  if (!artifacts.apolloAccountId && typeof firstContact.account_id === "string") artifacts.apolloAccountId = firstContact.account_id;
  void action;
}

async function apolloPrerequisites(
  credentials: Record<string, string>,
  artifacts: RuntimeArtifacts,
  report: Report,
) {
  const apiKey = credentials.apiKey;
  const calls = [
    { name: "email accounts", endpoint: "/email_accounts", method: "GET", body: undefined },
    { name: "sequences", endpoint: "/emailer_campaigns/search", method: "POST", body: { page: 1, per_page: 25 } },
    { name: "accounts", endpoint: "/accounts/search", method: "POST", body: { page: 1, per_page: 25 } },
  ] as const;
  for (const call of calls) {
    const started = Date.now();
    try {
      const response = await fetch(`https://api.apollo.io/api/v1${call.endpoint}`, {
        method: call.method,
        headers: { Accept: "application/json", "Content-Type": "application/json", "x-api-key": apiKey },
        body: call.body ? JSON.stringify(call.body) : undefined,
        signal: AbortSignal.timeout(30_000),
      });
      const text = await response.text();
      let body: unknown;
      try { body = text ? JSON.parse(text) : {}; } catch { body = text; }
      const root = record(body);
      if (call.name === "email accounts") {
        const accounts = records(root.email_accounts);
        const own = accounts.find((item) => String(item.email ?? "").toLowerCase() === TEST_DATA.email) ?? accounts[0];
        if (typeof own?.id === "string") artifacts.apolloEmailAccountId = own.id;
        if (typeof own?.user_id === "string") artifacts.apolloUserId = own.user_id;
      } else if (call.name === "sequences") {
        const sequences = records(root.emailer_campaigns ?? root.campaigns);
        const sequence = sequences.find((item) => item.active === true) ?? sequences[0];
        if (typeof sequence?.id === "string") artifacts.apolloSequenceId = sequence.id;
      } else {
        const accounts = records(root.accounts);
        const candidate = accounts.find((item) => String(item.domain ?? item.primary_domain ?? "").includes(TEST_DATA.domain)) ?? accounts[0];
        if (typeof candidate?.id === "string") artifacts.apolloAccountId = candidate.id;
      }
      report.prerequisiteCalls.push({
        provider: "apollo",
        name: call.name,
        endpoint: call.endpoint,
        status: response.ok ? "passed" : "failed",
        httpStatus: response.status,
        durationMs: Date.now() - started,
        response: sanitize(body),
      });
    } catch (error) {
      report.prerequisiteCalls.push({
        provider: "apollo",
        name: call.name,
        endpoint: call.endpoint,
        status: "failed",
        durationMs: Date.now() - started,
        error: error instanceof Error ? error.message : String(error),
      });
    }
    await save(report);
  }
}

const APOLLO_ORDER = [
  "find-person-by-email",
  "find-work-email",
  "enrich-person-from-linkedin",
  "enrich-company-by-domain",
  "find-user-id-by-email",
  "find-email-accounts-for-user",
  "find-people-at-company-by-job-title",
  "find-saved-contacts",
  "find-or-create-contact",
  "update-contact",
  "find-contact-by-id",
  "find-open-jobs",
  "find-account-by-id",
  "add-contact-to-sequence",
  "update-contact-status-in-sequence",
] as const;

function orderedActions(integration: IntegrationDefinition) {
  if (integration.key !== "apollo") return [...integration.actions];
  const byKey = new Map(integration.actions.map((action) => [action.key, action]));
  return APOLLO_ORDER.map((key) => byKey.get(key)).filter(Boolean) as IntegrationActionDefinition[];
}

async function main() {
  const { listIntegrationConnections, getIntegrationCredentials } = await import("../src/lib/grid/providers");
  const { getIntegrationActionHandler } = await import("../src/lib/integrations/server/registry");
  const integrations = integrationFilter
    ? INTEGRATIONS.filter((integration) => integration.key === integrationFilter)
    : [...INTEGRATIONS];
  if (integrationFilter && integrations.length === 0) throw new Error(`Unknown integration: ${integrationFilter}`);

  const totalActions = integrations.reduce(
    (sum, integration) => sum + integration.actions.filter((action) => !actionFilter || action.key === actionFilter).length,
    0,
  );
  const report: Report = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    testData: TEST_DATA,
    safety: {
      credentialValuesRecorded: false,
      notes: [
        "Only the supplied person's/company's real data is used.",
        "Apollo contact creation uses run_dedupe=true; contact updates avoid changing identity/company fields.",
        "If a sequence is available, the supplied email is enrolled and immediately stopped.",
        "Missing connections or workspace prerequisites are recorded as blocked, never replaced by invented IDs.",
      ],
    },
    summary: { totalIntegrations: integrations.length, totalActions, passed: 0, failed: 0, blocked: 0 },
    connections: [],
    prerequisiteCalls: [],
    actions: [],
  };
  const artifacts: RuntimeArtifacts = {};
  await save(report);

  for (const integration of integrations) {
    const connections = await listIntegrationConnections(integration.key);
    const connection = connections.find((item) => item.enabled && item.configured && item.verified);
    report.connections.push(connection
      ? { integrationKey: integration.key, connectionId: connection.id, connectionName: connection.name, available: true }
      : { integrationKey: integration.key, available: false, reason: "No enabled, configured, verified connection" });
    await save(report);

    const actions = orderedActions(integration).filter((action) => !actionFilter || action.key === actionFilter);
    if (!connection) {
      for (const action of actions) {
        const now = new Date().toISOString();
        const inputs = resolveInputs(action, artifacts);
        const issues = inputIssues(action, inputs);
        report.actions.push({
          integrationKey: integration.key,
          integrationName: integration.name,
          actionKey: action.key,
          actionName: action.name,
          handlerKey: action.handlerKey,
          docsUrl: action.docsUrl,
          status: "blocked",
          startedAt: now,
          finishedAt: now,
          durationMs: 0,
          inputs,
          inputContract: { valid: issues.length === 0, issues },
          blockedReason: "No enabled, configured, verified integration connection",
        });
      }
      await save(report);
      continue;
    }

    let credentials: Record<string, string> | null = null;
    let credentialError: string | null = null;
    try {
      credentials = await getIntegrationCredentials(connection.id);
    } catch (error) {
      credentialError = error instanceof Error ? error.message : String(error);
    }
    if (!credentials && integration.key === "apollo" && process.env.APOLLO_API_KEY) {
      credentials = { apiKey: process.env.APOLLO_API_KEY };
      report.prerequisiteCalls.push({
        provider: "apollo",
        name: "credential resolution",
        status: "passed_with_environment_fallback",
        note: "The stored credential could not be decrypted with the local key; APOLLO_API_KEY was used without recording its value.",
      });
    }
    if (!credentials) {
      const connectionRecord = report.connections.find((item) => item.connectionId === connection.id);
      if (connectionRecord) {
        connectionRecord.available = false;
        connectionRecord.reason = credentialError
          ? "Stored credential cannot be decrypted with the configured local encryption key"
          : "Verified connection did not resolve credentials";
      }
      for (const action of actions) {
        const now = new Date().toISOString();
        const inputs = resolveInputs(action, artifacts);
        const issues = inputIssues(action, inputs);
        report.actions.push({
          integrationKey: integration.key,
          integrationName: integration.name,
          actionKey: action.key,
          actionName: action.name,
          handlerKey: action.handlerKey,
          docsUrl: action.docsUrl,
          status: "blocked",
          startedAt: now,
          finishedAt: now,
          durationMs: 0,
          connection: { id: connection.id, name: connection.name },
          inputs,
          inputContract: { valid: issues.length === 0, issues },
          blockedReason: credentialError
            ? "Stored credential cannot be decrypted with the configured local encryption key; reconnect this integration"
            : "Verified connection did not resolve credentials",
        });
      }
      await save(report);
      continue;
    }
    if (integration.key === "apollo") await apolloPrerequisites(credentials, artifacts, report);

    for (const action of actions) {
      const startedAt = new Date().toISOString();
      const started = Date.now();
      const inputs = resolveInputs(action, artifacts);
      const issues = inputIssues(action, inputs);
      const missingRequired = action.inputs.filter((input) =>
        input.required && (inputs[input.key] === undefined || inputs[input.key] === null || inputs[input.key] === ""),
      );
      const base = {
        integrationKey: integration.key,
        integrationName: integration.name,
        actionKey: action.key,
        actionName: action.name,
        handlerKey: action.handlerKey,
        docsUrl: action.docsUrl,
        startedAt,
        connection: { id: connection.id, name: connection.name },
        inputs,
        inputContract: { valid: issues.length === 0, issues },
      };
      if (missingRequired.length || issues.length) {
        const finishedAt = new Date().toISOString();
        report.actions.push({
          ...base,
          status: "blocked",
          finishedAt,
          durationMs: Date.now() - started,
          blockedReason: missingRequired.length
            ? `Missing prerequisite inputs: ${missingRequired.map((item) => item.key).join(", ")}`
            : `Test inputs failed local contract: ${issues.join("; ")}`,
        });
        await save(report);
        continue;
      }

      const handler = getIntegrationActionHandler(action.handlerKey);
      if (!handler) {
        const finishedAt = new Date().toISOString();
        report.actions.push({
          ...base,
          status: "failed",
          finishedAt,
          durationMs: Date.now() - started,
          error: { name: "MissingHandler", message: "No registered server handler" },
        });
        await save(report);
        continue;
      }

      const config: EnrichmentConfig = {
        integrationKey: integration.key,
        actionKey: action.key,
        handlerKey: action.handlerKey,
        inputs: Object.fromEntries(action.inputs.map((input) => [input.key, { source: "column", columnKey: input.key }])),
        outputs: Object.fromEntries(action.outputs.map((output) => [output.key, output.key])),
        connectionId: connection.id,
      };
      try {
        let attempts = 0;
        let providerState: Record<string, unknown> | null = null;
        let result: CellResult | PendingCellResult;
        do {
          attempts += 1;
          result = await handler({
            config,
            action,
            inputs,
            credentials,
            connectionId: connection.id,
            providerState,
            timeoutMs: Math.min(action.async?.timeoutMs ?? 120_000, 300_000),
          });
          if (!isPending(result)) break;
          providerState = result.state;
          await sleep(Math.max(250, result.pollAfterMs));
        } while (attempts < 80);
        if (isPending(result!)) throw new Error("Action remained pending after 80 polls");
        const contractIssues = outputIssues(action, result!);
        if (integration.key === "apollo") extractApolloArtifacts(action, result!, artifacts);
        const sideEffect = action.handlerKey === "apollo.findOrCreateContact"
          ? "Found or created a deduplicated Apollo contact for the supplied email"
          : action.handlerKey === "apollo.updateContact"
            ? "Patched the Apollo contact using the supplied test profile fields"
            : action.handlerKey === "apollo.addContactToSequence"
              ? "Added the supplied email's contact to an existing Apollo sequence"
              : action.handlerKey === "apollo.updateContactStatusInSequence"
                ? "Stopped the supplied email's contact in the tested Apollo sequence"
                : undefined;
        report.actions.push({
          ...base,
          status: contractIssues.length ? "failed" : "passed",
          finishedAt: new Date().toISOString(),
          durationMs: Date.now() - started,
          attempts,
          outputContract: { valid: contractIssues.length === 0, issues: contractIssues },
          outcome: result!.outcome,
          value: sanitize(result!.value),
          outputs: sanitize(result!.outputs) as Record<string, unknown>,
          request: sanitize(result!.request),
          response: sanitize(result!.response),
          sideEffect,
        });
      } catch (error) {
        report.actions.push({
          ...base,
          status: "failed",
          finishedAt: new Date().toISOString(),
          durationMs: Date.now() - started,
          error: {
            name: error instanceof Error ? error.name : "Error",
            message: error instanceof Error ? error.message : String(error),
          },
        });
      }
      await save(report);
      const latest = report.actions.at(-1)!;
      console.log(`${latest.status.toUpperCase()} ${integration.key}/${action.key} (${latest.durationMs}ms)`);
    }
  }

  report.completedAt = new Date().toISOString();
  await save(report);
  if (mergePath) {
    const merged = JSON.parse(await readFile(mergePath, "utf8")) as Report;
    for (const result of report.actions) {
      const index = merged.actions.findIndex((item) =>
        item.integrationKey === result.integrationKey && item.actionKey === result.actionKey,
      );
      if (index >= 0) merged.actions[index] = result;
      else merged.actions.push(result);
    }
    for (const connection of report.connections) {
      const index = merged.connections.findIndex((item) => item.integrationKey === connection.integrationKey);
      if (index >= 0) merged.connections[index] = connection;
      else merged.connections.push(connection);
    }
    merged.prerequisiteCalls.push(...report.prerequisiteCalls);
    merged.completedAt = new Date().toISOString();
    summarize(merged);
    await writeFile(mergePath, `${JSON.stringify(sanitize(merged), null, 2)}\n`, "utf8");
  }
  console.log(`Report: ${reportPath}`);
  console.log(JSON.stringify(report.summary));
}

await runScriptInOrganization(main);
