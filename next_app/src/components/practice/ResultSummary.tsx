import { Card, CardContent } from "@/components/ui/card";

type ResultSummaryProps = {
  total: number;
  answered: number;
  correct: number;
};

export function ResultSummary({ total, answered, correct }: ResultSummaryProps) {
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card className="border border-slate-200 bg-white/80 shadow-sm">
        <CardContent className="space-y-1 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Score
          </p>
          <p className="text-2xl font-semibold text-foreground">{accuracy}%</p>
        </CardContent>
      </Card>
      <Card className="border border-slate-200 bg-white/80 shadow-sm">
        <CardContent className="space-y-1 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Correct
          </p>
          <p className="text-2xl font-semibold text-foreground">{correct}</p>
        </CardContent>
      </Card>
      <Card className="border border-slate-200 bg-white/80 shadow-sm">
        <CardContent className="space-y-1 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Answered
          </p>
          <p className="text-2xl font-semibold text-foreground">{answered}</p>
        </CardContent>
      </Card>
      <Card className="border border-slate-200 bg-white/80 shadow-sm">
        <CardContent className="space-y-1 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Total
          </p>
          <p className="text-2xl font-semibold text-foreground">{total}</p>
        </CardContent>
      </Card>
    </div>
  );
}
