import { useState } from "react";
import { Pin, StickyNote, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addIncidentNote, deleteIncidentNote, listIncidentNotes, updateIncidentNote } from "../../../api/incidentsApi";
import { queryKeys } from "../../../api/queryKeys";
import { Button } from "../../../components/ui/Button";
import { Card, CardBody } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../../components/ui/Alert";
import { Select } from "../../../components/ui/Select";
import { SkeletonCard } from "../../../components/ui/Skeleton";
import { Textarea } from "../../../components/ui/Textarea";
import { formatDateTime, titleCase } from "../../../utils/formatters";

const NOTE_TYPE_OPTIONS = [
  { value: "general", label: "General" },
  { value: "investigation", label: "Investigation" },
  { value: "decision", label: "Decision" },
  { value: "follow_up", label: "Follow-up" },
];

export function NotesTab({ incidentId }: { incidentId: string }) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [noteType, setNoteType] = useState("general");

  const notesQuery = useQuery({
    queryKey: queryKeys.incidentNotes(incidentId),
    queryFn: () => listIncidentNotes(incidentId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.incidentNotes(incidentId) });

  const addMutation = useMutation({
    mutationFn: () => addIncidentNote(incidentId, { note_type: noteType, content }),
    onSuccess: () => {
      setContent("");
      invalidate();
    },
  });

  const pinMutation = useMutation({
    mutationFn: ({ noteId, isPinned }: { noteId: string; isPinned: boolean }) =>
      updateIncidentNote(noteId, { is_pinned: !isPinned }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (noteId: string) => deleteIncidentNote(noteId),
    onSuccess: invalidate,
  });

  const notes = [...(notesQuery.data ?? [])].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    return (b.created_at ?? "").localeCompare(a.created_at ?? "");
  });

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardBody>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (content.trim()) addMutation.mutate();
            }}
            className="flex flex-col gap-3"
          >
            <Textarea
              label="Add a note"
              placeholder="Record investigation notes, decisions, or follow-ups…"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              rows={3}
            />
            <div className="flex items-center justify-between gap-3">
              <Select
                options={NOTE_TYPE_OPTIONS}
                value={noteType}
                onChange={(event) => setNoteType(event.target.value)}
                className="w-48"
              />
              <Button type="submit" isLoading={addMutation.isPending} disabled={!content.trim()}>
                Add note
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      {notesQuery.isLoading ? (
        <SkeletonCard />
      ) : notesQuery.isError ? (
        <ErrorRetryAlert message="Failed to load notes." onRetry={() => notesQuery.refetch()} />
      ) : notes.length === 0 ? (
        <EmptyState icon={StickyNote} title="No notes yet" description="Add the first investigation note above." />
      ) : (
        <div className="flex flex-col gap-3">
          {notes.map((note) => (
            <Card key={note.id}>
              <CardBody>
                <div className="flex items-start justify-between gap-2">
                  <span className="rounded-full bg-surface-interactive px-2 py-0.5 text-xs font-medium text-text-secondary">
                    {titleCase(note.note_type)}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => pinMutation.mutate({ noteId: note.id, isPinned: note.is_pinned })}
                      aria-label={note.is_pinned ? "Unpin note" : "Pin note"}
                      className={`rounded p-1 hover:bg-surface-hover ${note.is_pinned ? "text-warning" : "text-text-muted"}`}
                    >
                      <Pin className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteMutation.mutate(note.id)}
                      aria-label="Delete note"
                      className="rounded p-1 text-text-muted hover:bg-danger/10 hover:text-danger"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-text-secondary">{note.content}</p>
                <p className="mt-2 text-xs text-text-disabled">{formatDateTime(note.created_at)}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
