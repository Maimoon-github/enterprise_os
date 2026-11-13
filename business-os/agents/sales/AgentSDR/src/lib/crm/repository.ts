import { db } from "@/lib/db";

/** The concrete transaction handle produced by the application's only pool. */
export type CrmTransaction = Parameters<Parameters<typeof db.transaction>[0]>[0];

/** Shared query surface for read helpers that may run inside a larger transaction. */
export type CrmExecutor = Pick<
  CrmTransaction,
  "select" | "insert" | "update" | "delete" | "execute"
>;

export class CrmNotFoundError extends Error {
  constructor(entity: string, id: string) {
    super(`${entity} ${id} was not found`);
    this.name = "CrmNotFoundError";
  }
}

export class CrmConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CrmConflictError";
  }
}

export async function withCrmTransaction<T>(
  callback: (tx: CrmTransaction) => Promise<T>,
): Promise<T> {
  return db.transaction(callback);
}

