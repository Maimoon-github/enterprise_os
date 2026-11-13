const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

const envPath = path.join(__dirname, "../.env.local");
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, "utf8");
  for (const line of envContent.split(/\r?\n/)) {
    const match = line.match(/^([^#=\s]+)\s*=\s*(.*)$/);
    if (match) process.env[match[1].trim()] = match[2].trim().replace(/^"|"$/g, "");
  }
}

function normalizeDomain(input) {
  let value = String(input || "").trim().toLowerCase();
  value = value.replace(/^https?:\/\//, "").replace(/^\/\//, "");
  value = value.split(/[/?#]/)[0] || "";
  value = value.replace(/:\d+$/, "").replace(/\.$/, "");
  return value.replace(/^www\./, "");
}

const client = new Client({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
});

async function main() {
  await client.connect();
  await client.query("begin");

  const rowsResult = await client.query(`
    SELECT id, domain, parent_id, parent_domain
    FROM targeted_domains
    ORDER BY checked_at ASC NULLS LAST
  `);
  const rows = rowsResult.rows;
  let normalizedDomains = 0;
  let normalizedParentDomains = 0;
  let removedSelfParents = 0;
  let skippedConflicts = 0;

  for (const row of rows) {
    if (row.parent_domain) {
      const normalizedParent = normalizeDomain(row.parent_domain);
      if (normalizedParent && normalizedParent !== row.parent_domain) {
        await client.query("UPDATE targeted_domains SET parent_domain = $1 WHERE id = $2", [
          normalizedParent,
          row.id,
        ]);
        normalizedParentDomains += 1;
      }
    }
  }

  for (const row of rows) {
    const normalized = normalizeDomain(row.domain);
    if (!normalized || normalized === row.domain) continue;

    const conflict = await client.query(
      "SELECT id, is_parent_company FROM targeted_domains WHERE domain = $1 LIMIT 1",
      [normalized],
    );

    if (conflict.rows[0]) {
      const conflictRow = conflict.rows[0];
      const isSelfParent = row.parent_id === conflictRow.id;
      if (isSelfParent) {
        const otherChildren = await client.query(
          "SELECT count(*)::int AS count FROM targeted_domains WHERE parent_id = $1 AND id <> $2",
          [conflictRow.id, row.id],
        );
        if (otherChildren.rows[0].count > 0) {
          skippedConflicts += 1;
          continue;
        }

        await client.query(
          `UPDATE targeted_domains
           SET parent_id = NULL, parent_domain = NULL
           WHERE id = $1`,
          [row.id],
        );
        await client.query("DELETE FROM targeted_domains WHERE id = $1", [conflictRow.id]);
        await client.query("UPDATE targeted_domains SET domain = $1 WHERE id = $2", [
          normalized,
          row.id,
        ]);
        normalizedDomains += 1;
        removedSelfParents += 1;
      } else {
        skippedConflicts += 1;
      }
      continue;
    }

    await client.query("UPDATE targeted_domains SET domain = $1 WHERE id = $2", [
      normalized,
      row.id,
    ]);
    normalizedDomains += 1;
  }

  await client.query(`
    UPDATE targeted_domains
    SET parent_id = NULL, parent_domain = NULL
    WHERE parent_domain IS NOT NULL AND parent_domain = domain
  `);

  await client.query("commit");

  const counts = await client.query(`
    SELECT
      count(*)::int AS total,
      count(*) FILTER (WHERE domain LIKE 'www.%')::int AS www_domains,
      count(*) FILTER (WHERE parent_domain LIKE 'www.%')::int AS www_parent_domains
    FROM targeted_domains
  `);

  console.log(
    JSON.stringify(
      {
        normalizedDomains,
        normalizedParentDomains,
        removedSelfParents,
        skippedConflicts,
        counts: counts.rows[0],
      },
      null,
      2,
    ),
  );
}

main()
  .catch(async (err) => {
    try {
      await client.query("rollback");
    } catch {}
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await client.end();
  });
