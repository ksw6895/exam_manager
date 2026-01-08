import { useCallback, useMemo } from "react";

import type { Block, LectureSort, NormalizedLecture } from "@/components/lectures/types";
import { normalizeLecture } from "@/components/lectures/types";
import { LectureCard } from "@/components/lectures/LectureCard";
import { LectureEmptyState } from "@/components/lectures/LectureEmptyState";
import { LectureHeader } from "@/components/lectures/LectureHeader";
import { useLectureQuestionCounts } from "@/components/lectures/useLectureQuestionCounts";

type LectureGridProps = {
  blocks: Block[];
  query: string;
  onQueryChange: (value: string) => void;
  sort: LectureSort;
  onSortChange: (value: LectureSort) => void;
};

type NormalizedBlock = {
  blockId?: number | string;
  title?: string;
  lectures: NormalizedLecture[];
};

export function LectureGrid({
  blocks,
  query,
  onQueryChange,
  sort,
  onSortChange,
}: LectureGridProps) {
  const normalizedBlocks = useMemo<NormalizedBlock[]>(
    () =>
      (blocks ?? []).map((block) => ({
        blockId: block.blockId as number | string | undefined,
        title:
          typeof block.title === "string"
            ? block.title
            : typeof block.title === "number"
              ? String(block.title)
              : undefined,
        lectures: (block.lectures ?? []).map((lecture) => normalizeLecture(lecture)),
      })),
    [blocks]
  );

  const allLectures = useMemo(
    () => normalizedBlocks.flatMap((block) => block.lectures),
    [normalizedBlocks]
  );

  const counts = useLectureQuestionCounts(allLectures);

  const filteredBlocks = useMemo<NormalizedBlock[]>(() => {
    const term = query.trim().toLowerCase();
    if (!term) return normalizedBlocks;

    return normalizedBlocks
      .map((block) => {
        const blockTitle = block.title ?? "";
        const blockMatch = blockTitle.toLowerCase().includes(term);
        const lectures = block.lectures.filter((lecture) =>
          (lecture.title ?? "").toLowerCase().includes(term)
        );

        if (blockMatch) {
          return { ...block, lectures: block.lectures };
        }

        if (lectures.length > 0) {
          return { ...block, lectures };
        }

        return null;
      })
      .filter((block): block is NormalizedBlock => Boolean(block));
  }, [normalizedBlocks, query]);

  const getLectureCount = useCallback(
    (lecture: NormalizedLecture) => {
      if (lecture.id === null || lecture.id === undefined) {
        return typeof lecture.questionCount === "number" ? lecture.questionCount : null;
      }
      const cached = counts[String(lecture.id)];
      if (typeof cached === "number") return cached;
      return typeof lecture.questionCount === "number" ? lecture.questionCount : null;
    },
    [counts]
  );

  const sortedBlocks = useMemo<NormalizedBlock[]>(() => {
    return filteredBlocks.map((block) => {
      const lectures = [...block.lectures];
      if (sort === "questions") {
        lectures.sort((a, b) => {
          const countA = getLectureCount(a);
          const countB = getLectureCount(b);
          const valueA = typeof countA === "number" ? countA : -1;
          const valueB = typeof countB === "number" ? countB : -1;
          if (valueA !== valueB) return valueB - valueA;
          return (a.title ?? "").localeCompare(b.title ?? "", undefined, {
            sensitivity: "base",
          });
        });
      } else {
        lectures.sort((a, b) =>
          (a.title ?? "").localeCompare(b.title ?? "", undefined, { sensitivity: "base" })
        );
      }
      return { ...block, lectures };
    });
  }, [filteredBlocks, sort, getLectureCount]);

  const totalCount = useMemo(() => {
    return normalizedBlocks.reduce((sum, block) => sum + block.lectures.length, 0);
  }, [normalizedBlocks]);

  const filteredCount = useMemo(() => {
    return filteredBlocks.reduce((sum, block) => sum + block.lectures.length, 0);
  }, [filteredBlocks]);

  const hasLectures = sortedBlocks.some((block) => block.lectures.length > 0);

  return (
    <div className="space-y-8">
      <LectureHeader
        query={query}
        onQueryChange={onQueryChange}
        sort={sort}
        onSortChange={onSortChange}
        totalCount={totalCount}
        filteredCount={filteredCount}
      />

      {!hasLectures ? (
        <LectureEmptyState />
      ) : (
        <div className="space-y-10">
          {sortedBlocks.map((block, blockIndex) => {
            const blockKey = block.blockId ?? block.title ?? `block-${blockIndex}`;
            const blockTitle = block.title?.trim();
            const showHeader = Boolean(blockTitle) || sortedBlocks.length > 1;
            return (
              <section key={blockKey} className="space-y-4">
                {showHeader && (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
                        Block
                      </p>
                      <h2 className="text-xl font-semibold text-foreground">
                        {blockTitle ?? "Untitled Block"}
                      </h2>
                    </div>
                    <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
                      {block.lectures.length} lectures
                    </span>
                  </div>
                )}
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {block.lectures.map((lecture, lectureIndex) => (
                    <LectureCard
                      key={lecture.id ?? lecture.title ?? `${blockKey}-${lectureIndex}`}
                      lecture={lecture}
                      questionCount={getLectureCount(lecture)}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
