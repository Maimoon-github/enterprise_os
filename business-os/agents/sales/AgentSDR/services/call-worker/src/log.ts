export function log(...parts: unknown[]): void {
  console.log(new Date().toISOString(), ...parts);
}
