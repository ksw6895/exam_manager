import { Bookmark, BookmarkCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChoiceList } from "@/components/practice/ChoiceList";
import type { AnswerPayload, PracticeQuestion } from "@/components/practice/types";

type QuestionViewProps = {
  question: PracticeQuestion;
  index: number;
  total: number;
  answer?: AnswerPayload;
  onAnswerChange: (payload: AnswerPayload | undefined) => void;
  bookmarked?: boolean;
  onToggleBookmark?: () => void;
};

export function QuestionView({
  question,
  index,
  total,
  answer,
  onAnswerChange,
  bookmarked,
  onToggleBookmark,
}: QuestionViewProps) {
  const isShortAnswer = Boolean(question.isShortAnswer);
  const selectedValues =
    answer && answer.type === "mcq" && Array.isArray(answer.value) ? answer.value : [];
  const shortAnswerValue = answer && answer.type === "short" ? answer.value : "";
  const image = question.imageUrl ?? question.image;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Question {index + 1} of {total}
          </p>
          <h2 className="text-xl font-semibold text-foreground">Solve the question</h2>
        </div>
        {onToggleBookmark && (
          <Button
            variant={bookmarked ? "secondary" : "outline"}
            size="sm"
            onClick={onToggleBookmark}
            className="rounded-full"
          >
            {bookmarked ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
            {bookmarked ? "Bookmarked" : "Bookmark"}
          </Button>
        )}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="space-y-4">
          <p className="text-base leading-relaxed text-slate-800">
            {question.stem ?? "No prompt available for this question."}
          </p>
          {typeof image === "string" && image.length > 0 && (
            <img
              src={image}
              alt="Question visual"
              className="max-h-64 rounded-xl border border-slate-200 object-contain"
            />
          )}
        </div>
      </div>
      {isShortAnswer ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-foreground">Your answer</p>
          <Input
            value={shortAnswerValue}
            onChange={(event) =>
              onAnswerChange({
                type: "short",
                value: event.target.value,
              })
            }
            placeholder="Type your answer"
          />
        </div>
      ) : (
        <ChoiceList
          choices={question.choices ?? []}
          multiple={Boolean(question.isMultipleResponse)}
          selected={selectedValues}
          onChange={(next) => {
            onAnswerChange(
              next.length > 0
                ? {
                    type: "mcq",
                    value: next,
                  }
                : undefined
            );
          }}
        />
      )}
    </div>
  );
}
