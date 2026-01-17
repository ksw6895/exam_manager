CREATE TABLE IF NOT EXISTS question_queries (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    prompt_version TEXT NOT NULL,
    lecture_style_query TEXT NOT NULL,
    keywords_json TEXT NOT NULL,
    negative_keywords_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (question_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_question_queries_question_id
    ON question_queries(question_id);
