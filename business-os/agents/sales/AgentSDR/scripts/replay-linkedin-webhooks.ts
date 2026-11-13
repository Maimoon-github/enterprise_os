import { replayLinkedinWebhooks } from "../src/jobs/replayLinkedinWebhooks";

async function main() {
  if (!process.argv.includes("--apply")) {
    throw new Error("Refusing to mutate webhook state without --apply");
  }
  const limitArg = process.argv.find((arg) => arg.startsWith("--limit="));
  const limit = limitArg ? Number(limitArg.slice("--limit=".length)) : 100;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 1_000) {
    throw new Error("--limit must be an integer between 1 and 1000");
  }
  console.log(JSON.stringify(await replayLinkedinWebhooks(limit), null, 2));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
