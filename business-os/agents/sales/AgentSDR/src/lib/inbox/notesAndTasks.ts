import { and, eq, desc } from "drizzle-orm";
import { db } from "@/lib/db";
import { inboxTasks, inboxNotes, inboxContacts } from "@/lib/inbox/schema";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

export async function listTasks() {
  const rows = await db
    .select({
      id: inboxTasks.id,
      leadId: inboxTasks.contactId,
      name: inboxTasks.name,
      description: inboxTasks.description,
      isCompleted: inboxTasks.isCompleted,
      createdAt: inboxTasks.createdAt,
      leadEmail: inboxContacts.email,
      leadFirstName: inboxContacts.firstName,
      leadLastName: inboxContacts.lastName,
    })
    .from(inboxTasks)
    .leftJoin(inboxContacts, and(eq(inboxTasks.contactId, inboxContacts.id), inOrg(inboxContacts)))
    .where(inOrg(inboxTasks))
    .orderBy(desc(inboxTasks.createdAt));
  return rows;
}

export async function createTask(input: { leadId?: string | null; name: string; description?: string | null }) {
  const [row] = await db
    .insert(inboxTasks)
    .values({ organizationId: currentOrganizationId(), contactId: input.leadId ?? null, name: input.name.trim(), description: input.description ?? null })
    .returning();
  return row;
}

export async function updateTask(id: string, patch: { name?: string; description?: string | null; isCompleted?: boolean }) {
  await db.update(inboxTasks).set({ ...patch, updatedAt: new Date() }).where(and(inOrg(inboxTasks), eq(inboxTasks.id, id)));
}

export async function deleteTask(id: string) {
  await db.delete(inboxTasks).where(and(inOrg(inboxTasks), eq(inboxTasks.id, id)));
}

export async function listNotes() {
  const rows = await db
    .select({
      id: inboxNotes.id,
      leadId: inboxNotes.contactId,
      title: inboxNotes.title,
      description: inboxNotes.description,
      createdAt: inboxNotes.createdAt,
      leadEmail: inboxContacts.email,
      leadFirstName: inboxContacts.firstName,
      leadLastName: inboxContacts.lastName,
    })
    .from(inboxNotes)
    .leftJoin(inboxContacts, and(eq(inboxNotes.contactId, inboxContacts.id), inOrg(inboxContacts)))
    .where(inOrg(inboxNotes))
    .orderBy(desc(inboxNotes.createdAt));
  return rows;
}

export async function createNote(input: { leadId?: string | null; title: string; description?: string | null }) {
  const [row] = await db
    .insert(inboxNotes)
    .values({ organizationId: currentOrganizationId(), contactId: input.leadId ?? null, title: input.title.trim(), description: input.description ?? null })
    .returning();
  return row;
}

export async function updateNote(id: string, patch: { title?: string; description?: string | null }) {
  await db.update(inboxNotes).set({ ...patch, updatedAt: new Date() }).where(and(inOrg(inboxNotes), eq(inboxNotes.id, id)));
}

export async function deleteNote(id: string) {
  await db.delete(inboxNotes).where(and(inOrg(inboxNotes), eq(inboxNotes.id, id)));
}
