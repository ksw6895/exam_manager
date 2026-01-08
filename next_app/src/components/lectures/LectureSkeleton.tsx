import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function LectureSkeleton() {
  return (
    <div className="space-y-10">
      {[0, 1].map((section) => (
        <section key={section} className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-6 w-44" />
            </div>
            <Skeleton className="h-6 w-24 rounded-full" />
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Card key={index} className="h-full">
                <CardHeader className="space-y-4">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-5 w-40" />
                </CardHeader>
                <CardContent className="flex items-center justify-between">
                  <Skeleton className="h-7 w-32 rounded-full" />
                  <Skeleton className="h-9 w-24 rounded-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
