import Link from "next/link";
import { BookOpen, ListChecks } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { NormalizedLecture } from "@/components/lectures/types";

type LectureCardProps = {
  lecture: NormalizedLecture;
  questionCount?: number | null;
};

export function LectureCard({ lecture, questionCount }: LectureCardProps) {
  const resolvedCount =
    typeof questionCount === "number"
      ? questionCount
      : typeof lecture.questionCount === "number"
        ? lecture.questionCount
        : null;
  const countLabel = typeof resolvedCount === "number" ? `${resolvedCount}` : "—";
  const lectureId = lecture.id;
  const startHref =
    lectureId !== null && lectureId !== undefined
      ? `/practice/start?lectureId=${encodeURIComponent(String(lectureId))}`
      : null;

  return (
    <Card className="group flex h-full flex-col border border-slate-200/70 bg-white/80 shadow-sm backdrop-blur transition hover:-translate-y-0.5 hover:shadow-md">
      <CardHeader className="space-y-4">
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            <span>Lecture</span>
          </div>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] text-slate-600">
            Ready
          </span>
        </div>
        <CardTitle className="text-lg leading-snug text-foreground">
          {lecture.title ?? "Untitled Lecture"}
        </CardTitle>
      </CardHeader>
      <CardContent className="mt-auto flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
          <ListChecks className="h-4 w-4" />
          <span className="text-base font-semibold text-foreground">{countLabel}</span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Questions
          </span>
        </div>
        {startHref ? (
          <Button size="sm" className="rounded-full px-4" asChild>
            <Link href={startHref}>Study</Link>
          </Button>
        ) : (
          <Button size="sm" className="rounded-full px-4" disabled>
            Study
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
