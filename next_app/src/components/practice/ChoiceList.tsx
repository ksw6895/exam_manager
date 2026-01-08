import { cn } from "@/lib/utils";

import type { PracticeChoice } from "@/components/practice/types";

type ChoiceListProps = {
  choices: PracticeChoice[];
  multiple?: boolean;
  selected: number[];
  onChange: (next: number[]) => void;
};

const getChoiceId = (choice: PracticeChoice, index: number) =>
  typeof choice.number === "number" ? choice.number : index + 1;

export function ChoiceList({ choices, multiple, selected, onChange }: ChoiceListProps) {
  return (
    <div className="space-y-3">
      {choices.map((choice, index) => {
        const choiceId = getChoiceId(choice, index);
        const checked = selected.includes(choiceId);
        const label = choice.content ?? `Choice ${choiceId}`;
        const image = choice.imageUrl ?? choice.image;

        const toggle = () => {
          if (multiple) {
            const next = checked
              ? selected.filter((value) => value !== choiceId)
              : [...selected, choiceId];
            onChange(next);
          } else {
            onChange([choiceId]);
          }
        };

        return (
          <label
            key={choiceId}
            className={cn(
              "flex cursor-pointer gap-3 rounded-2xl border px-4 py-3 text-sm transition",
              checked
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-700 hover:border-slate-400"
            )}
          >
            <input
              type={multiple ? "checkbox" : "radio"}
              name="practice-choice"
              checked={checked}
              onChange={toggle}
              className="mt-1 h-4 w-4 accent-slate-900"
            />
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                {choiceId}
              </div>
              <p className="text-sm leading-relaxed">{label}</p>
              {typeof image === "string" && image.length > 0 && (
                <img
                  src={image}
                  alt={`Choice ${choiceId}`}
                  className="max-h-48 rounded-lg border border-slate-200 object-contain"
                />
              )}
            </div>
          </label>
        );
      })}
    </div>
  );
}
