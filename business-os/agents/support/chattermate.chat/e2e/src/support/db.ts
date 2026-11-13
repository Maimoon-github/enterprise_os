import { execFileSync } from 'node:child_process'
import { env } from '../env'

/**
 * Direct SQL on the throwaway e2e database, for state no API sets — e.g. moving
 * a timestamp past a deadline a worker checks. Keep it rare; seed through src/api.
 */
export function sql(query: string): string {
  return execFileSync('psql', [env.databaseUrl, '-v', 'ON_ERROR_STOP=1', '-qtA', '-c', query], { encoding: 'utf8' }).trim()
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Guards every id interpolated into SQL. */
export function uuid(value: string): string {
  if (!UUID.test(value)) throw new Error(`not a UUID: ${value}`)
  return value
}
