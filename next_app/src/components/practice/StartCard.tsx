import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type PracticeMode = "practice" | "timed";

type StartCardProps = {
  title?: string;
  questionCount?: number;
  mode: PracticeMode;
  onModeChange: (mode: PracticeMode) => void;
  onStart: () => void;
  loading?: boolean;
  error?: string | null;
};

export function StartCard({
  title,
  questionCount,
  mode,
  onModeChange,
  onStart,
  loading,
  error,
}: StartCardProps) {
  return (
    <Card className="w-full max-w-2xl border border-slate-200/70 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          Practice Session
        </p>
        <CardTitle className="text-2xl text-foreground">Start your session</CardTitle>
        <CardDescription className="text-sm text-muted-foreground">
          {title ?? "Pick a lecture to begin your practice run."}
        </CardDescription>
        {typeof questionCount === "number" && (
          <span className="inline-flex w-fit rounded-full bg-secondary px-3 py-1 text-xs font-semibold text-secondary-foreground">
            {questionCount} questions available
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2">
          {(
            [
              {
                value: "practice",
                title: "Practice",
                description: "Review questions at your own pace.",
              },
              {
                value: "timed",
                title: "Timed",
                description: "Simulate test conditions with a timer.",
              },
            ] as const
          ).map((option) => {
            const active = mode === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => onModeChange(option.value)}
                className={`rounded-2xl border p-4 text-left transition ${
                  active
                    ? "border-slate-900 bg-slate-900 text-white shadow-lg"
                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-400"
                }`}
              >
                <p className="text-base font-semibold">{option.title}</p>
                <p className={`text-xs ${active ? "text-slate-200" : "text-muted-foreground"}`}>
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>
        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}
        <Button
          onClick={onStart}
          disabled={loading}
          className="w-full rounded-full py-6 text-base font-semibold"
        >
          {loading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Starting...
            </>
          ) : (
            "Start exam"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
