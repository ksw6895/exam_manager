import Link from "next/link";

import { getBlockLectures } from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function ManageBlockLecturesPage({ params }: PageProps) {
  try {
    const { id } = await params;
    const data = await getBlockLectures(id);
    const block = data.block;

    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              Block
            </p>
            <h2 className="text-2xl font-semibold text-foreground">{block.name}</h2>
            {block.description && (
              <p className="mt-2 text-sm text-muted-foreground">{block.description}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="neutral">{data.lectures.length} lectures</Badge>
            <Button asChild>
              <Link href={`/manage/blocks/${block.id}/lectures/new`}>New lecture</Link>
            </Button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.lectures.map((lecture) => (
            <Card key={lecture.id} className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-3 p-5">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  <span>Lecture</span>
                </div>
                <div>
                  <Link
                    href={`/manage/lectures/${lecture.id}`}
                    className="text-lg font-semibold text-foreground hover:underline"
                  >
                    {lecture.title}
                  </Link>
                  {lecture.professor && (
                    <p className="text-xs text-muted-foreground">{lecture.professor}</p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge variant="neutral">{lecture.questionCount ?? 0} questions</Badge>
                  <Badge variant="success">{lecture.classifiedCount ?? 0} classified</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load lectures.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Lectures unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
