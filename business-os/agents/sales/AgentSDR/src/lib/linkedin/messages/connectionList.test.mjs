import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { PgDialect } from "drizzle-orm/pg-core";
import {
  UNREPLIED_FILTER,
  parseConnectionListFilters,
} from "./connectionList.ts";
import { buildConnectionListWhere } from "./connectionList.server.ts";
import { runInOrganization } from "../../tenancy/scope.ts";

describe("LinkedIn message filters", () => {
  it("parses the unreplied filter from the connections request", () => {
    const filters = parseConnectionListFilters(
      new URLSearchParams({ status: UNREPLIED_FILTER })
    );

    assert.equal(filters.status, UNREPLIED_FILTER);
  });

  it("defines unreplied as the latest canonical inbound message", () => {
    const where = runInOrganization("00000000-0000-0000-0000-00000000000a", () =>
      buildConnectionListWhere({ status: UNREPLIED_FILTER })
    );
    assert.ok(where);

    const { sql } = new PgDialect().sqlToQuery(where);
    assert.match(sql, /SELECT DISTINCT ON \(m\."connectionId"\)/);
    assert.match(sql, /m\."duplicateOfMessageId" IS NULL/);
    assert.match(sql, /ORDER BY m\."connectionId", m\."createdAt" DESC, m\."id" DESC/);
    assert.match(sql, /latest\."type" = 'RECEIVED'/);
  });
});
