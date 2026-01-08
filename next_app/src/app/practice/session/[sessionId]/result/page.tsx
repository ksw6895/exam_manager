"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { apiFetch } from "@/lib/http";
import { ResultSummary } from "@/components/practice/ResultSummary";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  AnswerPayload,
  lectureResultSchema,
  PracticeQuestion,
} from "@/components/practice/types";

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";

type StoredResult = {
  lectureId?: string;
  submittedAt?: string;
  summary?: {
    all?: {
      total?: number;
      answered?: number;
      correct?: number;
    };
  };
  items?: unknown[];
  answers?: Record<string, AnswerPayload>;
  mode?: string;
};

type ResultItem = {
  questionId: string;
  type?: string;
  isAnswered?: boolean;
  isCorrect?: boolean | null;
  userAnswer?: unknown;
  correctAnswer?: unknown;
  correctAnswerText?: string | null;
};

type ResultQuestion = PracticeQuestion & {
  explanation?: string | null;
  correctChoiceNumbers?: number[];
  correctAnswerText?: string | null;
};

const normalizeResultItem = (raw: unknown): ResultItem | null => {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const rawId = record.questionId ?? record.question_id;
  if (typeof rawId !== "string" && typeof rawId !== "number") return null;
  return {
    questionId: String(rawId),
    type: typeof record.type === "string" ? record.type : undefined,
    isAnswered: typeof record.isAnswered === "boolean" ? record.isAnswered : undefined,
    isCorrect: typeof record.isCorrect === "boolean" ? record.isCorrect : null,
    userAnswer: record.userAnswer,
    correctAnswer: record.correctAnswer,
    correctAnswerText:
      typeof record.correctAnswerText === "string" ? record.correctAnswerText : null,
  };
};

const formatAnswer = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  return "—";
};

export default function PracticeResultPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [storedResult, setStoredResult] = useState<StoredResult | null>(null);
  const [questions, setQuestions] = useState<ResultQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"all" | "wrong">("all");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = sessionStorage.getItem(`practice:result:${sessionId}`);
    if (stored) {
      try {
        setStoredResult(JSON.parse(stored));
      } catch {
        setStoredResult(null);
      }
    }
  }, [sessionId]);

  useEffect(() => {
    let active = true;
    const loadResult = async () => {
      if (!storedResult?.lectureId) {
        setLoading(false);
        setError("Result data missing. Please submit again.");
        return;
      }

      try {
        const response = await apiFetch<unknown>(
          `/api/practice/lecture/${encodeURIComponent(
            storedResult.lectureId
          )}/result?includeAnswer=true`,
          { cache: "no-store" }
        );
        const parsed = lectureResultSchema.safeParse(response);
        if (!parsed.success) {
          throw new Error(CONNECTION_ERROR_MESSAGE);
        }
        if (!active) return;
        setQuestions((parsed.data.questions ?? []) as ResultQuestion[]);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
      } finally {
        if (active) setLoading(false);
      }
    };

    void loadResult();

    return () => {
      active = false;
    };
  }, [storedResult?.lectureId]);

  const resultItems = useMemo(() => {
    const items = storedResult?.items ?? [];
    return items
      .map(normalizeResultItem)
      .filter((item): item is ResultItem => Boolean(item));
  }, [storedResult?.items]);

  const itemsById = useMemo(() => {
    const map = new Map<string, ResultItem>();
    resultItems.forEach((item) => {
      map.set(item.questionId, item);
    });
    return map;
  }, [resultItems]);

  const combinedQuestions = useMemo(() => {
    if (!questions.length) return [];
    return questions.map((question) => ({
      ...question,
      result: itemsById.get(String(question.questionId)),
    }));
  }, [questions, itemsById]);

  const filteredQuestions = useMemo(() => {
    if (tab === "all") return combinedQuestions;
    return combinedQuestions.filter((question) => question.result?.isCorrect === false);
  }, [combinedQuestions, tab]);

  const summary = storedResult?.summary?.all;
  const total = summary?.total ?? resultItems.length;
  const answered =
    summary?.answered ??
    resultItems.filter((item) => item.isAnswered || item.userAnswer).length;
  const correct = summary?.correct ?? resultItems.filter((item) => item.isCorrect).length;

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 px-4 py-10">
        <div className="mx-auto w-full max-w-5xl space-y-6">
          <div className="h-10 w-40 animate-pulse rounded-full bg-slate-200" />
          <div className="h-32 animate-pulse rounded-3xl bg-slate-200" />
          <div className="h-64 animate-pulse rounded-3xl bg-slate-200" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 px-4 py-10">
        <div className="mx-auto w-full max-w-3xl">
          <Card className="border border-destructive/30 bg-destructive/10">
            <CardContent className="space-y-2 p-6">
              <p className="text-lg font-semibold text-foreground">Unable to load results</p>
              <p className="text-sm text-muted-foreground">{error}</p>
              <Button onClick={() => router.back()} className="mt-4">
                Go back
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 px-4 py-10">
      <div className="mx-auto w-full max-w-5xl space-y-8">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            Result
          </p>
          <h1 className="text-3xl font-semibold text-foreground">Session summary</h1>
          <p className="text-sm text-muted-foreground">
            Review your answers and revisit incorrect questions.
          </p>
        </div>

        <ResultSummary total={total} answered={answered} correct={correct} />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex rounded-full border border-slate-200 bg-white p-1 text-sm">
            <button
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                tab === "all" ? "bg-slate-900 text-white" : "text-slate-600"
              }`}
              onClick={() => setTab("all")}
              type="button"
            >
              All
            </button>
            <button
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                tab === "wrong" ? "bg-slate-900 text-white" : "text-slate-600"
              }`}
              onClick={() => setTab("wrong")}
              type="button"
            >
              Wrong only
            </button>
          </div>
          <Button variant="outline">Retry wrong answers</Button>
        </div>

        <div className="space-y-6">
          {filteredQuestions.map((question, index) => {
            const result = question.result;
            const isCorrect = result?.isCorrect;
            const userAnswer = result?.userAnswer;
            const correctAnswers =
              question.correctChoiceNumbers ?? (Array.isArray(result?.correctAnswer)
                ? result?.correctAnswer
                : []);
            const correctAnswerText =
              question.correctAnswerText ?? result?.correctAnswerText ?? null;
            return (
              <Card key={question.questionId} className="border border-slate-200 bg-white/90">
                <CardContent className="space-y-4 p-6">
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>Question {index + 1}</span>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${
                        isCorrect === true
                          ? "bg-emerald-100 text-emerald-700"
                          : isCorrect === false
                            ? "bg-rose-100 text-rose-700"
                            : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {isCorrect === true
                        ? "Correct"
                        : isCorrect === false
                          ? "Wrong"
                          : "Pending"}
                    </span>
                  </div>
                  <p className="text-base text-slate-800">
                    {question.stem ?? "No prompt available."}
                  </p>

                  {question.isShortAnswer ? (
                    <div className="space-y-2 text-sm">
                      <p className="text-muted-foreground">Your answer: {formatAnswer(userAnswer)}</p>
                      <p className="text-muted-foreground">
                        Correct answer: {formatAnswer(correctAnswerText)}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2 text-sm">
                      <p className="text-muted-foreground">Your answer: {formatAnswer(userAnswer)}</p>
                      <p className="text-muted-foreground">
                        Correct answer: {formatAnswer(correctAnswers)}
                      </p>
                      <div className="space-y-2">
                        {(question.choices ?? []).map((choice, choiceIndex) => {
                          const choiceId =
                            typeof choice.number === "number" ? choice.number : choiceIndex + 1;
                          const isUserChoice = Array.isArray(userAnswer)
                            ? userAnswer.includes(choiceId)
                            : false;
                          const isCorrectChoice = Array.isArray(correctAnswers)
                            ? correctAnswers.includes(choiceId)
                            : false;
                          return (
                            <div
                              key={choiceId}
                              className={`rounded-xl border px-4 py-3 ${
                                isCorrectChoice
                                  ? "border-emerald-400 bg-emerald-50"
                                  : isUserChoice
                                    ? "border-rose-300 bg-rose-50"
                                    : "border-slate-200 bg-white"
                              }`}
                            >
                              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                {choiceId}
                              </div>
                              <p className="text-sm text-slate-700">
                                {choice.content ?? "Choice"}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {question.explanation && (
                    <details className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
                      <summary className="cursor-pointer font-semibold text-slate-700">
                        Explanation
                      </summary>
                      <p className="mt-2 text-slate-600">{question.explanation}</p>
                    </details>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
