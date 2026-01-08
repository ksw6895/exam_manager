import { BookMarked } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function LectureEmptyState() {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <div className="rounded-full bg-secondary p-3 text-secondary-foreground">
          <BookMarked className="h-6 w-6" />
        </div>
        <div className="space-y-1">
          <p className="text-base font-semibold text-foreground">No lectures found</p>
          <p className="text-sm text-muted-foreground">
            Try adjusting your search or check back after adding more content.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
