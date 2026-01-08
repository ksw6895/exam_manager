"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/http";
import type { Block, Lecture, LectureSort } from "@/components/lectures/types";
import { LectureGrid } from "@/components/lectures/LectureGrid";
import { LectureSkeleton } from "@/components/lectures/LectureSkeleton";
import { LectureErrorState } from "@/components/lectures/LectureErrorState";

type LecturesResponse =
  | {
      blocks?: Block[];
      ok?: boolean;
      data?: unknown;
    }
  | unknown[];

export default function LecturesPage() {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<LectureSort>("title");

  useEffect(() => {
    let active = true;

    apiFetch<LecturesResponse>("/api/practice/lectures", { cache: "no-store" })
      .then((response) => {
        if (!active) return;
        if (Array.isArray(response)) {
          setBlocks([{ title: "Lectures", lectures: response as Lecture[] }]);
          return;
        }
        if (response && typeof response === "object") {
          if (Array.isArray(response.blocks)) {
            setBlocks(response.blocks);
            return;
          }
          if (Array.isArray(response.data)) {
            setBlocks([{ title: "Lectures", lectures: response.data as Lecture[] }]);
            return;
          }
        }
        setBlocks([{ title: "Lectures", lectures: [] }]);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load lectures.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100">
      <div className="mx-auto w-full max-w-6xl px-4 pb-16 pt-12">
        {loading && <LectureSkeleton />}
        {!loading && error && <LectureErrorState message={error} />}
        {!loading && !error && (
          <LectureGrid
            blocks={blocks}
            query={query}
            onQueryChange={setQuery}
            sort={sort}
            onSortChange={setSort}
          />
        )}
      </div>
    </div>
  );
}
