import { z } from "zod";

export const choiceSchema = z
  .object({
    number: z.number().optional(),
    content: z.string().optional(),
    image: z.string().optional(),
    imageUrl: z.string().optional(),
  })
  .passthrough();

export type PracticeChoice = z.infer<typeof choiceSchema>;

export const questionSchema = z
  .object({
    questionId: z.union([z.number(), z.string()]),
    stem: z.string().optional(),
    choices: z.array(choiceSchema).optional(),
    isShortAnswer: z.boolean().optional(),
    isMultipleResponse: z.boolean().optional(),
    image: z.string().optional(),
    imageUrl: z.string().optional(),
  })
  .passthrough();

export type PracticeQuestion = z.infer<typeof questionSchema> & {
  questionId: number | string;
};

export const lectureDetailSchema = z
  .object({
    lectureId: z.union([z.number(), z.string()]).optional(),
    title: z.string().optional(),
    questions: z.array(z.any()).optional(),
  })
  .passthrough();

export const lectureQuestionsResponseSchema = z
  .object({
    lectureId: z.union([z.number(), z.string()]).optional(),
    title: z.string().optional(),
    total: z.number().optional(),
    offset: z.number().optional(),
    limit: z.number().optional(),
    questions: z.array(questionSchema).optional(),
  })
  .passthrough();

export const lectureResultSchema = z
  .object({
    lectureId: z.union([z.number(), z.string()]).optional(),
    title: z.string().optional(),
    total: z.number().optional(),
    offset: z.number().optional(),
    limit: z.number().optional(),
    questions: z
      .array(
        questionSchema.extend({
          explanation: z.string().nullable().optional(),
          correctChoiceNumbers: z.array(z.number()).optional(),
          correctAnswerText: z.string().nullable().optional(),
        })
      )
      .optional(),
  })
  .passthrough();

export const sessionDetailSchema = z
  .object({
    sessionId: z.union([z.number(), z.string()]).optional(),
    lectureId: z.union([z.number(), z.string()]).optional(),
    lectureTitle: z.string().optional(),
    mode: z.string().optional(),
    questionOrder: z.array(z.number()).optional(),
    totalQuestions: z.number().optional(),
  })
  .passthrough();

export type AnswerPayload =
  | {
      type: "mcq";
      value: number[];
    }
  | {
      type: "short";
      value: string;
    };

export const submitResponseSchema = z
  .object({
    lectureId: z.union([z.number(), z.string()]).optional(),
    submittedAt: z.string().optional(),
    summary: z
      .object({
        all: z
          .object({
            total: z.number().optional(),
            answered: z.number().optional(),
            correct: z.number().optional(),
          })
          .partial()
          .optional(),
      })
      .partial()
      .optional(),
    items: z.array(z.any()).optional(),
  })
  .passthrough();
