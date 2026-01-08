import { useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/http";
import type { NormalizedLecture } from "@/components/lectures/types";

type CountMap = Record<string, number | null>;

const questionCountCache = new Map<string, number | null>();
const inflightRequests = new Map<string, Promise<number | null>>();
const MAX_CONCURRENCY = 5;

const COUNT_KEYS = [
  "total",
  "totalCount",
  "count",
  "questionCount",
  "question_count",
  "numQuestions",
  "num_questions",
];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const toNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
};

const readCountFrom = (record: Record<string, unknown>): number | null => {
  for (const key of COUNT_KEYS) {
    if (!(key in record)) continue;
    const parsed = toNumber(record[key]);
    if (parsed !== null) return parsed;
  }
  return null;
};

const extractCountFromResponse = (payload: unknown): number | null => {
  if (!isRecord(payload)) return null;

  const direct = readCountFrom(payload);
  if (direct !== null) return direct;

  const nestedCandidates = ["data", "meta", "pagination", "page", "result"];
  for (const key of nestedCandidates) {
    const nested = payload[key];
    if (!isRecord(nested)) continue;
    const nestedCount = readCountFrom(nested);
    if (nestedCount !== null) return nestedCount;
  }

  return null;
};

const runWithConcurrency = async (
  tasks: Array<() => Promise<void>>,
  limit: number
) => {
  let index = 0;
  const workers = Array.from({ length: Math.min(limit, tasks.length) }, async () => {
    while (index < tasks.length) {
      const taskIndex = index;
      index += 1;
      await tasks[taskIndex]?.();
    }
  });

  await Promise.all(workers);
};

const fetchQuestionCount = async (lectureId: string | number): Promise<number | null> => {
  const key = String(lectureId);
  if (questionCountCache.has(key)) {
    return questionCountCache.get(key) ?? null;
  }
  const existing = inflightRequests.get(key);
  if (existing) return existing;

  const request = apiFetch<unknown>(
    `/api/practice/lecture/${encodeURIComponent(String(lectureId))}/questions?limit=1&offset=0`,
    { cache: "no-store" }
  )
    .then((payload) => extractCountFromResponse(payload))
    .catch(() => null)
    .finally(() => {
      inflightRequests.delete(key);
    });

  inflightRequests.set(key, request);
  const count = await request;
  questionCountCache.set(key, count);
  return count;
};

export function useLectureQuestionCounts(lectures: NormalizedLecture[]) {
  const [counts, setCounts] = useState<CountMap>({});

  const lectureIds = useMemo(
    () =>
      lectures
        .map((lecture) => {
          if (lecture.id === null || lecture.id === undefined) return null;
          return {
            id: lecture.id,
            key: String(lecture.id),
            initialCount: lecture.questionCount,
          };
        })
        .filter((entry): entry is { id: string | number; key: string; initialCount?: number } =>
          Boolean(entry)
        ),
    [lectures]
  );

  useEffect(() => {
    if (lectureIds.length === 0) return;
    let cancelled = false;

    setCounts((prev) => {
      let next = prev;
      for (const lecture of lectureIds) {
        if (typeof lecture.initialCount === "number") {
          questionCountCache.set(lecture.key, lecture.initialCount);
        }
        const cached = questionCountCache.get(lecture.key) ?? null;
        if (prev[lecture.key] !== cached) {
          if (next === prev) next = { ...prev };
          next[lecture.key] = cached;
        }
      }
      return next;
    });

    const pending = lectureIds.filter((lecture) => {
      if (typeof lecture.initialCount === "number") return false;
      return !questionCountCache.has(lecture.key);
    });

    if (pending.length === 0) return;

    const tasks = pending.map((lecture) => async () => {
      const count = await fetchQuestionCount(lecture.id);
      if (cancelled) return;
      setCounts((prev) => {
        if (prev[lecture.key] === count) return prev;
        return { ...prev, [lecture.key]: count };
      });
    });

    void runWithConcurrency(tasks, MAX_CONCURRENCY);

    return () => {
      cancelled = true;
    };
  }, [lectureIds]);

  return counts;
}
