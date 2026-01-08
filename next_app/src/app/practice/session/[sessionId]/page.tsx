"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Flag, Timer } from "lucide-react";

import { apiFetch } from "@/lib/http";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { QuestionView } from "@/components/practice/QuestionView";
import { SubmitDialog } from "@/components/practice/SubmitDialog";
import {
  AnswerPayload,
  lectureQuestionsResponseSchema,
  PracticeQuestion,
  sessionDetailSchema,
  submitResponseSchema,
} from "@/components/practice/types";

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";
const PAGE_SIZE = 200;

type SessionContext = {
  lectureId?: string;
  lectureTitle?: string;
  mode?: string;
  fallback?: boolean;
  warning?: string | null;
  source?: string;
  questionOrder?: number[];
};

type SubmitResult = {
  lectureId?: string;
  submittedAt?: string;
  summary?: unknown;
  items?: unknown[];
};

const formatTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
};

const getChoiceId = (choice: { number?: number }, index: number) =>
  typeof choice.number === "number" ? choice.number : index + 1;

export default function PracticeSessionPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [sessionContext, setSessionContext] = useState<SessionContext>({});
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [questionOrder, setQuestionOrder] = useState<number[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, AnswerPayload>>({});
  const [bookmarks, setBookmarks] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [loadMoreLoading, setLoadMoreLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showSubmitDialog, setShowSubmitDialog] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [pagination, setPagination] = useState({
    total: 0,
    offset: 0,
    limit: PAGE_SIZE,
    hasMore: false,
  });

  const fallbackLectureId = useMemo(() => {
    if (sessionId?.startsWith("lecture-")) {
      return decodeURIComponent(sessionId.replace("lecture-", ""));
    }
    return null;
  }, [sessionId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = sessionStorage.getItem(`practice:session:${sessionId}`);
    if (stored) {
      try {
        setSessionContext(JSON.parse(stored));
      } catch {
        setSessionContext({});
      }
    }
  }, [sessionId]);

  useEffect(() => {
    const timerId = setInterval(() => {
      setTimerSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timerId);
  }, []);

  const fetchQuestions = useCallback(
    async (lectureId: string, offset = 0) => {
      const response = await apiFetch<unknown>(
        `/api/practice/lecture/${encodeURIComponent(
          lectureId
        )}/questions?limit=${PAGE_SIZE}&offset=${offset}`,
        { cache: "no-store" }
      );
      const parsed = lectureQuestionsResponseSchema.safeParse(response);
      if (!parsed.success) {
        throw new Error(CONNECTION_ERROR_MESSAGE);
      }
      const data = parsed.data;
      return {
        questions: data.questions ?? [],
        total: data.total ?? 0,
        offset: data.offset ?? offset,
        limit: data.limit ?? PAGE_SIZE,
      };
    },
    []
  );

  useEffect(() => {
    let active = true;

    const loadSession = async () => {
      setLoading(true);
      setError(null);
      setSubmitError(null);

      let lectureId = sessionContext.lectureId ?? fallbackLectureId ?? undefined;
      let order = sessionContext.questionOrder ?? [];

      if (!lectureId && sessionId && !sessionId.startsWith("lecture-")) {
        try {
          const response = await apiFetch<unknown>(
            `/api/practice/sessions/${encodeURIComponent(sessionId)}`,
            { cache: "no-store" }
          );
          const parsed = sessionDetailSchema.safeParse(response);
          if (parsed.success) {
            lectureId =
              parsed.data.lectureId !== undefined ? String(parsed.data.lectureId) : undefined;
            order = parsed.data.questionOrder ?? [];
            setSessionContext((prev) => ({
              ...prev,
              lectureId,
              lectureTitle: parsed.data.lectureTitle ?? prev.lectureTitle,
              mode: parsed.data.mode ?? prev.mode,
            }));
          }
        } catch {
          setSessionContext((prev) => ({
            ...prev,
            warning: prev.warning ?? CONNECTION_ERROR_MESSAGE,
          }));
        }
      }

      if (!lectureId) {
        setError("Unable to resolve lecture for this session.");
        setLoading(false);
        return;
      }

      try {
        const page = await fetchQuestions(lectureId, 0);
        if (!active) return;
        setQuestions(page.questions);
        setQuestionOrder(order);
        setPagination({
          total: page.total,
          offset: page.offset,
          limit: page.limit,
          hasMore: page.total > page.questions.length,
        });
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
      } finally {
        if (active) setLoading(false);
      }
    };

    void loadSession();

    return () => {
      active = false;
    };
  }, [fetchQuestions, fallbackLectureId, sessionContext.lectureId, sessionId, sessionContext.questionOrder]);

  const orderedQuestions = useMemo(() => {
    if (!questionOrder.length) return questions;
    const map = new Map(questions.map((question) => [String(question.questionId), question]));
    const ordered = questionOrder
      .map((id) => map.get(String(id)))
      .filter((item): item is PracticeQuestion => Boolean(item));
    const remaining = questions.filter(
      (question) => !questionOrder.includes(Number(question.questionId))
    );
    return [...ordered, ...remaining];
  }, [questions, questionOrder]);

  useEffect(() => {
    if (currentIndex >= orderedQuestions.length) {
      setCurrentIndex(0);
    }
  }, [currentIndex, orderedQuestions.length]);

  const currentQuestion = orderedQuestions[currentIndex];
  const progress = orderedQuestions.length
    ? Math.round(((currentIndex + 1) / orderedQuestions.length) * 100)
    : 0;

  const unansweredCount = useMemo(() => {
    return orderedQuestions.reduce((count, question) => {
      const answer = answers[String(question.questionId)];
      if (!answer) return count + 1;
      if (answer.type === "mcq" && answer.value.length === 0) return count + 1;
      if (answer.type === "short" && answer.value.trim().length === 0) return count + 1;
      return count;
    }, 0);
  }, [answers, orderedQuestions]);

  const handleAnswerChange = useCallback(
    (questionId: string, payload?: AnswerPayload) => {
      setAnswers((prev) => {
        const next = { ...prev };
        if (!payload) {
          delete next[questionId];
          return next;
        }
        if (payload.type === "mcq" && payload.value.length === 0) {
          delete next[questionId];
          return next;
        }
        if (payload.type === "short" && payload.value.trim().length === 0) {
          delete next[questionId];
          return next;
        }
        next[questionId] = payload;
        return next;
      });
    },
    []
  );

  const toggleBookmark = useCallback((questionId: string) => {
    setBookmarks((prev) => ({ ...prev, [questionId]: !prev[questionId] }));
  }, []);

  const handleKeyboard = useCallback(
    (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) {
        return;
      }
      if (!currentQuestion) return;

      const key = event.key.toLowerCase();
      if (key === "arrowright" || key === "j") {
        setCurrentIndex((prev) => Math.min(prev + 1, orderedQuestions.length - 1));
        return;
      }
      if (key === "arrowleft" || key === "k") {
        setCurrentIndex((prev) => Math.max(prev - 1, 0));
        return;
      }

      if (key >= "1" && key <= "5") {
        const index = Number(key) - 1;
        const choice = currentQuestion.choices?.[index];
        if (!choice) return;
        const choiceId = getChoiceId(choice, index);
        const current = answers[String(currentQuestion.questionId)];
        if (currentQuestion.isMultipleResponse) {
          const existing =
            current && current.type === "mcq" && Array.isArray(current.value)
              ? current.value
              : [];
          const next = existing.includes(choiceId)
            ? existing.filter((value) => value !== choiceId)
            : [...existing, choiceId];
          handleAnswerChange(String(currentQuestion.questionId), {
            type: "mcq",
            value: next,
          });
        } else {
          handleAnswerChange(String(currentQuestion.questionId), {
            type: "mcq",
            value: [choiceId],
          });
        }
      }
    },
    [answers, currentQuestion, handleAnswerChange, orderedQuestions.length]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyboard);
    return () => window.removeEventListener("keydown", handleKeyboard);
  }, [handleKeyboard]);

  const handleSubmit = async () => {
    const lectureId = sessionContext.lectureId ?? fallbackLectureId;
    if (!lectureId) {
      setSubmitError("Unable to resolve lecture for submission.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);

    const answersPayload: Record<string, AnswerPayload> = {};
    for (const [questionId, payload] of Object.entries(answers)) {
      if (payload.type === "mcq" && payload.value.length === 0) continue;
      if (payload.type === "short" && payload.value.trim().length === 0) continue;
      answersPayload[questionId] = payload;
    }

    const body = JSON.stringify({ version: 1, answers: answersPayload });
    const headers = { "Content-Type": "application/json" };

    const submitViaSession = async () =>
      apiFetch<unknown>(
        `/api/practice/sessions/${encodeURIComponent(sessionId)}/submit`,
        { method: "POST", headers, body }
      );

    const submitViaLecture = async () =>
      apiFetch<unknown>(
        `/api/practice/lecture/${encodeURIComponent(lectureId)}/submit`,
        { method: "POST", headers, body }
      );

    let response: unknown = null;
    try {
      if (!sessionId.startsWith("lecture-")) {
        response = await submitViaSession();
      }
    } catch {
      response = null;
    }

    if (!response) {
      try {
        response = await submitViaLecture();
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
        setSubmitting(false);
        return;
      }
    }

    const parsed = submitResponseSchema.safeParse(response);
    const resultPayload: SubmitResult = parsed.success
      ? {
          lectureId:
            parsed.data.lectureId !== undefined ? String(parsed.data.lectureId) : lectureId,
          submittedAt: parsed.data.submittedAt,
          summary: parsed.data.summary,
          items: parsed.data.items ?? [],
        }
      : {
          lectureId,
          summary: undefined,
          items: [],
        };

    if (typeof window !== "undefined") {
      sessionStorage.setItem(
        `practice:result:${sessionId}`,
        JSON.stringify({
          ...resultPayload,
          lectureId,
          answers: answersPayload,
          mode: sessionContext.mode,
        })
      );
    }

    router.push(`/practice/session/${sessionId}/result`);
  };

  const handleLoadMore = async () => {
    if (loadMoreLoading || !pagination.hasMore) return;
    const lectureId = sessionContext.lectureId ?? fallbackLectureId;
    if (!lectureId) return;
    setLoadMoreLoading(true);
    try {
      const nextOffset = pagination.offset + pagination.limit;
      const page = await fetchQuestions(lectureId, nextOffset);
      setQuestions((prev) => [...prev, ...page.questions]);
      setPagination({
        total: page.total,
        offset: page.offset,
        limit: page.limit,
        hasMore: nextOffset + page.questions.length < page.total,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
    } finally {
      setLoadMoreLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 px-4 py-10">
        <div className="mx-auto w-full max-w-5xl space-y-6">
          <div className="h-8 w-48 animate-pulse rounded-full bg-slate-200" />
          <div className="h-48 animate-pulse rounded-3xl bg-slate-200" />
          <div className="h-56 animate-pulse rounded-3xl bg-slate-200" />
        </div>
      </div>
    );
  }

  if (error || !currentQuestion) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 px-4 py-10">
        <div className="mx-auto w-full max-w-3xl">
          <Card className="border border-destructive/30 bg-destructive/10">
            <CardContent className="space-y-2 p-6">
              <p className="text-lg font-semibold text-foreground">Unable to load session</p>
              <p className="text-sm text-muted-foreground">
                {error ?? CONNECTION_ERROR_MESSAGE}
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const answerForCurrent = answers[String(currentQuestion.questionId)];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 px-4 py-10">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <div className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                {sessionContext.mode ?? "practice"}
              </p>
              <h1 className="text-2xl font-semibold text-foreground">
                {sessionContext.lectureTitle ?? "Practice Session"}
              </h1>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Timer className="h-4 w-4" />
                <span>{formatTime(timerSeconds)}</span>
              </div>
              <Button variant="outline" size="sm" onClick={() => setShowSubmitDialog(true)}>
                Submit
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {currentIndex + 1} / {orderedQuestions.length} questions
              </span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
              <div className="h-full bg-slate-900" style={{ width: `${progress}%` }} />
            </div>
          </div>
          {sessionContext.warning && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {sessionContext.warning}
            </div>
          )}
          {submitError && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {submitError}
            </div>
          )}
        </div>

        <QuestionView
          question={currentQuestion}
          index={currentIndex}
          total={orderedQuestions.length}
          answer={answerForCurrent}
          onAnswerChange={(payload) =>
            handleAnswerChange(String(currentQuestion.questionId), payload)
          }
          bookmarked={Boolean(bookmarks[String(currentQuestion.questionId)])}
          onToggleBookmark={() => toggleBookmark(String(currentQuestion.questionId))}
        />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button
            variant="outline"
            onClick={() => setCurrentIndex((prev) => Math.max(prev - 1, 0))}
            disabled={currentIndex === 0}
          >
            Previous
          </Button>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Flag className="h-4 w-4" />
            {bookmarks[String(currentQuestion.questionId)] ? "Bookmarked" : "Not bookmarked"}
          </div>
          <Button
            onClick={() =>
              setCurrentIndex((prev) => Math.min(prev + 1, orderedQuestions.length - 1))
            }
            disabled={currentIndex >= orderedQuestions.length - 1}
          >
            Next
          </Button>
        </div>

        {pagination.hasMore && (
          <div className="flex justify-center">
            <Button variant="outline" onClick={handleLoadMore} disabled={loadMoreLoading}>
              {loadMoreLoading ? "Loading more..." : "Load more questions"}
            </Button>
          </div>
        )}
      </div>

      <SubmitDialog
        open={showSubmitDialog}
        unansweredCount={unansweredCount}
        onClose={() => setShowSubmitDialog(false)}
        onConfirm={() => {
          setShowSubmitDialog(false);
          void handleSubmit();
        }}
        loading={submitting}
      />
    </div>
  );
}
