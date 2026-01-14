"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  createLecture,
  deleteLecture,
  updateLecture,
  type ManageLecture,
  type ManageLectureInput,
} from "@/lib/api/manage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type LectureFormProps = {
  blockId: string | number;
  initial?: ManageLecture | null;
};

export function LectureForm({ blockId, initial }: LectureFormProps) {
  const router = useRouter();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [professor, setProfessor] = useState(initial?.professor ?? "");
  const [order, setOrder] = useState(initial?.order ?? 1);
  const [description, setDescription] = useState(initial?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    const payload: ManageLectureInput = {
      title: title.trim(),
      professor: professor?.trim() || null,
      order: Number.isFinite(order) ? Number(order) : 1,
      description: description?.trim() || null,
    };
    try {
      if (initial?.id) {
        await updateLecture(initial.id, payload);
        setSuccess("Lecture updated.");
      } else {
        await createLecture(blockId, payload);
        setSuccess("Lecture created.");
      }
      router.push(`/manage/blocks/${blockId}/lectures`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save lecture.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!initial?.id) return;
    const confirmed = window.confirm("Delete this lecture? This cannot be undone.");
    if (!confirmed) return;
    setSaving(true);
    setError(null);
    try {
      await deleteLecture(initial.id);
      router.push(`/manage/blocks/${blockId}/lectures`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete lecture.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border border-border/70 bg-card/85 shadow-soft">
      <CardContent className="space-y-6 p-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Title
            </label>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Professor
            </label>
            <Input
              value={professor ?? ""}
              onChange={(event) => setProfessor(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Order
            </label>
            <Input
              type="number"
              value={order}
              onChange={(event) => setOrder(Number(event.target.value))}
            />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Description
          </label>
          <Textarea
            value={description ?? ""}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        {error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
            {success}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {initial?.id ? (
            <Button variant="outline" onClick={handleDelete} disabled={saving}>
              Delete lecture
            </Button>
          ) : (
            <div />
          )}
          <Button onClick={handleSubmit} disabled={saving || !title.trim()}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
