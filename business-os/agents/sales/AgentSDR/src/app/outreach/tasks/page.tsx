import NotesTasksClient from "@/components/inbox/NotesTasksClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Tasks" };

export default function TasksPage() {
  return (
    <div className="h-full px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
      <NotesTasksClient mode="tasks" />
    </div>
  );
}
