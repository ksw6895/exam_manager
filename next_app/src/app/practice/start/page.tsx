"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiFetch, HttpError } from "@/lib/http";
import { StartCard } from "@/components/practice/StartCard";
import { lectureDetailSchema } from "@/components/practice/types";

type PracticeMode = "practice" | "timed";

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";

const extractSessionId = (payload: unknown): string | number | null => {
  if (!payload || typeof payload !== "object") return null;
  const record = payload as Record<string, unknown>;
  const candidates = [
    record.sessionId,
    record.session_id,
    record.id,
    record.sessionID,
    record.session,
  ];
  for (const entry of candidates) {
    if (typeof entry === "string" || typeof entry === "number") {
      return entry;
    }
  }
  if (record.data && typeof record.data === "object") {
    const nested = record.data as Record<string, unknown>;
    const nestedId = nested.sessionId ?? nested.id;
    if (typeof nestedId === "string" || typeof nestedId === "number") {
      return nestedId;
    }
  }
  return null;
};

const createSession = async (lectureId: string, mode: PracticeMode) => {
  const payload = { lectureId, mode };
  const body = JSON.stringify(payload);
  const headers = { "Content-Type": "application/json" };
  const attempts = [
    {
      path: "/api/practice/sessions",
      init: { method: "POST", headers, body },
    },
    {
      path: `/api/practice/lecture/${encodeURIComponent(lectureId)}/start`,
      init: { method: "POST", headers, body },
    },
  ];

  let lastError: string | null = null;
  let unsupported = true;
  for (const attempt of attempts) {
    try {
      const result = await apiFetch<unknown>(attempt.path, attempt.init);
      const sessionId = extractSessionId(result);
      if (sessionId !== null) {
        return { sessionId, source: attempt.path };
      }
      unsupported = false;
      lastError = CONNECTION_ERROR_MESSAGE;
    } catch (error) {
      if (error instanceof HttpError) {
        if (error.payload.status === 404 || error.payload.status === 405) {
          continue;
        }
      }
      unsupported = false;
      lastError = error instanceof Error ? error.message : CONNECTION_ERROR_MESSAGE;
    }
  }

  return { sessionId: null, error: lastError ?? null, unsupported };
};

export default function PracticeStartPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const lectureIdParam = searchParams.get("lectureId");

  const [mode, setMode] = useState<PracticeMode>("practice");
  const [lectureTitle, setLectureTitle] = useState<string | undefined>();
  const [questionCount, setQuestionCount] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [startLoading, setStartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const safeLectureId = useMemo(() => lectureIdParam ?? "", [lectureIdParam]);

  useEffect(() => {
    let active = true;
    if (!lectureIdParam) {
      setLoading(false);
      setError("Missing lecture selection.");
      return;
    }

    apiFetch<unknown>(`/api/practice/lecture/${encodeURIComponent(lectureIdParam)}`, {
      cache: "no-store",
    })
      .then((payload) => {
        if (!active) return;
        const parsed = lectureDetailSchema.safeParse(payload);
        if (!parsed.success) {
          setLectureTitle(undefined);
          setQuestionCount(undefined);
          return;
        }
        setLectureTitle(parsed.data.title ?? "Lecture");
        if (Array.isArray(parsed.data.questions)) {
          setQuestionCount(parsed.data.questions.length);
        }
      })
      .catch(() => {
        if (!active) return;
        setError(CONNECTION_ERROR_MESSAGE);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [lectureIdParam]);

  const handleStart = async () => {
    if (!lectureIdParam) {
      setError("Missing lecture selection.");
      return;
    }
    setStartLoading(true);
    setError(null);

    const result = await createSession(lectureIdParam, mode);
    const sessionId =
      result.sessionId ?? `lecture-${encodeURIComponent(String(lectureIdParam))}`;
    const shouldWarn = result.sessionId === null && result.error && !result.unsupported;

    const sessionPayload = {
      lectureId: lectureIdParam,
      lectureTitle,
      mode,
      fallback: result.sessionId === null,
      createdAt: Date.now(),
      warning: shouldWarn ? result.error : null,
      source: result.sessionId === null ? "lecture-fallback" : result.source,
    };

    if (typeof window !== "undefined") {
      sessionStorage.setItem(
        `practice:session:${sessionId}`,
        JSON.stringify(sessionPayload)
      );
      if (shouldWarn) {
        sessionStorage.setItem(
          `practice:warning:${sessionId}`,
          result.error ?? CONNECTION_ERROR_MESSAGE
        );
      }
    }

    router.push(`/practice/session/${sessionId}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 px-4 py-12">
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-center gap-8">
        {loading ? (
          <div className="w-full max-w-2xl animate-pulse rounded-3xl border border-slate-200 bg-white/80 p-8">
            <div className="h-4 w-32 rounded-full bg-slate-200" />
            <div className="mt-4 h-6 w-64 rounded-full bg-slate-200" />
            <div className="mt-2 h-4 w-48 rounded-full bg-slate-200" />
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <div className="h-24 rounded-2xl bg-slate-200" />
              <div className="h-24 rounded-2xl bg-slate-200" />
            </div>
            <div className="mt-6 h-12 rounded-full bg-slate-200" />
          </div>
        ) : (
          <StartCard
            title={lectureTitle}
            questionCount={questionCount}
            mode={mode}
            onModeChange={setMode}
            onStart={handleStart}
            loading={startLoading}
            error={error}
          />
        )}
        {!safeLectureId && (
          <p className="text-sm text-muted-foreground">Select a lecture to continue.</p>
        )}
      </div>
    </div>
  );
}
