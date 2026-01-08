import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { LectureSort } from "@/components/lectures/types";

type LectureHeaderProps = {
  query: string;
  onQueryChange: (value: string) => void;
  sort: LectureSort;
  onSortChange: (value: LectureSort) => void;
  totalCount: number;
  filteredCount: number;
};

export function LectureHeader({
  query,
  onQueryChange,
  sort,
  onSortChange,
  totalCount,
  filteredCount,
}: LectureHeaderProps) {
  return (
    <div className="mb-8 space-y-6">
      <div className="space-y-4">
        <p className="text-xs font-semibold uppercase tracking-[0.4em] text-muted-foreground">
          Study Library
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold text-foreground">Lectures</h1>
            <p className="text-sm text-muted-foreground">
              {filteredCount} of {totalCount} lectures ready to study.
            </p>
          </div>
          <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
            <div className="relative w-full sm:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder="Search lectures"
                className="pl-10"
              />
            </div>
            <div className="w-full sm:w-48">
              <Select
                value={sort}
                onChange={(event) => onSortChange(event.target.value as LectureSort)}
                aria-label="Sort lectures"
              >
                <option value="title">Title (A-Z)</option>
                <option value="questions">Most questions</option>
              </Select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
