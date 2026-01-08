import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type SubmitDialogProps = {
  open: boolean;
  unansweredCount: number;
  onClose: () => void;
  onConfirm: () => void;
  loading?: boolean;
};

export function SubmitDialog({
  open,
  unansweredCount,
  onClose,
  onConfirm,
  loading,
}: SubmitDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md border border-slate-200 bg-white">
        <CardHeader className="space-y-2">
          <CardTitle className="text-lg">Submit your answers?</CardTitle>
          <p className="text-sm text-muted-foreground">
            You still have {unansweredCount} unanswered question
            {unansweredCount === 1 ? "" : "s"}.
          </p>
        </CardHeader>
        <CardContent className="flex items-center justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={loading}>
            {loading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Submitting...
              </>
            ) : (
              "Submit"
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
