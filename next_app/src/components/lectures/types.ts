export type Lecture = Record<string, unknown> & {
  id?: number | string;
  lectureId?: number | string;
  lecture_id?: number | string;
  title?: string;
  name?: string;
  questionCount?: number;
  question_count?: number;
  numQuestions?: number;
  num_questions?: number;
};

export type NormalizedLecture = {
  id?: number | string;
  title?: string;
  questionCount?: number;
};

export type Block = Record<string, unknown> & {
  blockId?: number | string;
  title?: string;
  lectures?: Lecture[];
};

export type LectureSort = "title" | "questions";

const LECTURE_ID_KEYS = ["id", "lectureId", "lecture_id", "lectureID", "uuid"];
const LECTURE_TITLE_KEYS = ["title", "name", "lectureTitle", "lecture_name"];
const QUESTION_COUNT_KEYS = [
  "questionCount",
  "question_count",
  "numQuestions",
  "num_questions",
  "totalQuestions",
  "total_questions",
  "totalQuestionCount",
  "total_question_count",
  "questionsCount",
  "questionTotal",
];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const toId = (value: unknown): string | number | undefined => {
  if (typeof value === "string" || typeof value === "number") {
    return value;
  }
  return undefined;
};

const toTitle = (value: unknown): string | undefined => {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return undefined;
};

const toNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
};

const pickFirst = <T>(
  record: Record<string, unknown>,
  keys: string[],
  parser: (value: unknown) => T | undefined
): T | undefined => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const parsed = parser(record[key]);
    if (parsed !== undefined) return parsed;
  }
  return undefined;
};

export function normalizeLecture(raw: unknown): NormalizedLecture {
  if (!isRecord(raw)) return {};

  return {
    id: pickFirst(raw, LECTURE_ID_KEYS, toId),
    title: pickFirst(raw, LECTURE_TITLE_KEYS, toTitle),
    questionCount: pickFirst(raw, QUESTION_COUNT_KEYS, toNumber),
  };
}
