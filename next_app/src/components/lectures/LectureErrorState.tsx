import { AlertTriangle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

type LectureErrorStateProps = {
  message: string;
};

export function LectureErrorState({ message }: LectureErrorStateProps) {
  return (
    <Card className="border-destructive/20 bg-destructive/5">
      <CardContent className="flex items-center gap-4 py-10">
        <div className="rounded-full bg-destructive/10 p-3 text-destructive">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div>
          <p className="text-base font-semibold text-foreground">Unable to load lectures</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </CardContent>
    </Card>
  );
}
