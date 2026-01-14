import { z } from "zod";

import { apiFetch } from "@/lib/http";

const blockSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().nullable().optional(),
  order: z.number().optional(),
  lectureCount: z.number().optional(),
  questionCount: z.number().optional(),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
});

const lectureSchema = z.object({
  id: z.number(),
  blockId: z.number(),
  blockName: z.string().nullable().optional(),
  title: z.string(),
  professor: z.string().nullable().optional(),
  order: z.number().optional(),
  description: z.string().nullable().optional(),
  questionCount: z.number().optional(),
  classifiedCount: z.number().optional(),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
});

const examSchema = z.object({
  id: z.number(),
  title: z.string(),
  examDate: z.string().nullable().optional(),
  subject: z.string().nullable().optional(),
  year: z.number().nullable().optional(),
  term: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  questionCount: z.number().optional(),
  classifiedCount: z.number().optional(),
  unclassifiedCount: z.number().optional(),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
});

const questionSchema = z.object({
  id: z.number(),
  questionNumber: z.number(),
  type: z.string().optional(),
  lectureId: z.number().nullable().optional(),
  lectureTitle: z.string().nullable().optional(),
  isClassified: z.boolean(),
  classificationStatus: z.string().nullable().optional(),
  hasImage: z.boolean().optional(),
});

const choiceSchema = z.object({
  id: z.number().optional(),
  number: z.number(),
  content: z.string().nullable().optional(),
  imagePath: z.string().nullable().optional(),
  isCorrect: z.boolean().optional(),
});

const questionDetailSchema = z.object({
  id: z.number(),
  examId: z.number(),
  examTitle: z.string().nullable().optional(),
  questionNumber: z.number(),
  type: z.string(),
  lectureId: z.number().nullable().optional(),
  lectureTitle: z.string().nullable().optional(),
  content: z.string().nullable().optional(),
  explanation: z.string().nullable().optional(),
  imagePath: z.string().nullable().optional(),
  answer: z.string().nullable().optional(),
  correctAnswerText: z.string().nullable().optional(),
  choices: z.array(choiceSchema),
});

const summarySchema = z.object({
  counts: z.object({
    blocks: z.number(),
    lectures: z.number(),
    exams: z.number(),
    questions: z.number(),
    unclassified: z.number(),
  }),
  recentExams: z.array(examSchema),
});

const blocksSchema = z.array(blockSchema);
const lecturesSchema = z.array(lectureSchema);
const examsSchema = z.array(examSchema);

const blockLecturesSchema = z.object({
  block: blockSchema,
  lectures: lecturesSchema,
});

const examDetailSchema = z.object({
  exam: examSchema,
  questions: z.array(questionSchema),
});

const uploadPdfSchema = z.object({
  examId: z.number(),
  questionCount: z.number(),
  choiceCount: z.number(),
});

const okResponse = <T extends z.ZodTypeAny>(schema: T) =>
  z.object({ ok: z.literal(true), data: schema });

export type ManageSummary = z.infer<typeof summarySchema>;
export type ManageBlock = z.infer<typeof blockSchema>;
export type ManageLecture = z.infer<typeof lectureSchema>;
export type ManageExam = z.infer<typeof examSchema>;
export type ManageQuestion = z.infer<typeof questionSchema>;
export type ManageChoice = z.infer<typeof choiceSchema>;
export type ManageQuestionDetail = z.infer<typeof questionDetailSchema>;
export type UploadPdfResult = z.infer<typeof uploadPdfSchema>;
export type ManageBlockInput = {
  name: string;
  description?: string | null;
  order?: number | null;
};
export type ManageLectureInput = {
  title: string;
  professor?: string | null;
  order?: number | null;
  description?: string | null;
};
export type ManageExamInput = {
  title: string;
  examDate?: string | null;
  subject?: string | null;
  year?: number | null;
  term?: string | null;
  description?: string | null;
};

export async function getManageSummary() {
  const payload = await apiFetch<unknown>("/api/manage/summary", { cache: "no-store" });
  return okResponse(summarySchema).parse(payload).data;
}

export async function getBlocks() {
  const payload = await apiFetch<unknown>("/api/manage/blocks", { cache: "no-store" });
  return okResponse(blocksSchema).parse(payload).data;
}

export async function getBlock(blockId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}`,
    { cache: "no-store" }
  );
  return okResponse(blockSchema).parse(payload).data;
}

export async function getBlockLectures(blockId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}/lectures`,
    { cache: "no-store" }
  );
  return okResponse(blockLecturesSchema).parse(payload).data;
}

export async function getLectures() {
  const payload = await apiFetch<unknown>("/api/manage/lectures", { cache: "no-store" });
  return okResponse(lecturesSchema).parse(payload).data;
}

export async function createBlock(input: ManageBlockInput) {
  const payload = await apiFetch<unknown>("/api/manage/blocks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return okResponse(blockSchema).parse(payload).data;
}

export async function updateBlock(blockId: string | number, input: ManageBlockInput) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(blockSchema).parse(payload).data;
}

export async function deleteBlock(blockId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}`,
    { method: "DELETE" }
  );
  return okResponse(z.object({ id: z.number() })).parse(payload).data;
}

export async function getLecture(lectureId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}`,
    { cache: "no-store" }
  );
  return okResponse(lectureSchema).parse(payload).data;
}

export async function createLecture(blockId: string | number, input: ManageLectureInput) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}/lectures`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(lectureSchema).parse(payload).data;
}

export async function updateLecture(lectureId: string | number, input: ManageLectureInput) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(lectureSchema).parse(payload).data;
}

export async function deleteLecture(lectureId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}`,
    { method: "DELETE" }
  );
  return okResponse(z.object({ id: z.number() })).parse(payload).data;
}

export async function getQuestionDetail(questionId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/questions/${encodeURIComponent(String(questionId))}`,
    { cache: "no-store" }
  );
  return okResponse(questionDetailSchema).parse(payload).data;
}

export type ManageQuestionUpdate = {
  content?: string | null;
  explanation?: string | null;
  type?: string | null;
  lectureId?: number | null;
  correctAnswerText?: string | null;
  uploadedImage?: string | null;
  removeImage?: boolean;
  choices?: ManageChoice[];
};

export async function updateQuestion(
  questionId: string | number,
  input: ManageQuestionUpdate
) {
  const payload = await apiFetch<unknown>(
    `/api/manage/questions/${encodeURIComponent(String(questionId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(questionDetailSchema).parse(payload).data;
}

export async function uploadPdf(formData: FormData) {
  const payload = await apiFetch<unknown>("/api/manage/upload-pdf", {
    method: "POST",
    body: formData,
  });
  return okResponse(uploadPdfSchema).parse(payload).data;
}

export async function getExams() {
  const payload = await apiFetch<unknown>("/api/manage/exams", { cache: "no-store" });
  return okResponse(examsSchema).parse(payload).data;
}

export async function getExamDetail(examId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/exams/${encodeURIComponent(String(examId))}`,
    { cache: "no-store" }
  );
  return okResponse(examDetailSchema).parse(payload).data;
}

export async function createExam(input: ManageExamInput) {
  const payload = await apiFetch<unknown>("/api/manage/exams", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return okResponse(examSchema).parse(payload).data;
}

export async function updateExam(examId: string | number, input: ManageExamInput) {
  const payload = await apiFetch<unknown>(
    `/api/manage/exams/${encodeURIComponent(String(examId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(examSchema).parse(payload).data;
}

export async function deleteExam(examId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/exams/${encodeURIComponent(String(examId))}`,
    { method: "DELETE" }
  );
  return okResponse(z.object({ id: z.number() })).parse(payload).data;
}
