import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { step } from './step'

const STACK = fileURLToPath(new URL('../../scripts/stack.sh', import.meta.url))

export type Worker = 'crm-sync' | 'knowledge' | 'ticket-lifecycle'

/**
 * Runs one pass of a background worker now (scripts/stack.sh tick), so a journey
 * that production completes on a worker's next poll completes here, at once.
 */
export async function runWorkerOnce(worker: Worker): Promise<void> {
  await step(`The ${worker} worker runs`, async () => {
    execFileSync(STACK, ['tick', worker], { env: process.env, stdio: 'pipe', timeout: 120_000 })
  })
}
