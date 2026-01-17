CREATE TABLE block_folders (
    id INTEGER PRIMARY KEY,
    block_id INTEGER NOT NULL,
    parent_id INTEGER,
    name TEXT NOT NULL,
    "order" INTEGER DEFAULT 0,
    description TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY(block_id) REFERENCES blocks(id),
    FOREIGN KEY(parent_id) REFERENCES block_folders(id)
);

CREATE INDEX idx_block_folders_block_parent_order
    ON block_folders (block_id, parent_id, "order");

ALTER TABLE lectures ADD COLUMN folder_id INTEGER REFERENCES block_folders(id);

CREATE TABLE question_chunk_matches (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL,
    lecture_id INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    material_id INTEGER,
    page_start INTEGER,
    page_end INTEGER,
    snippet TEXT,
    score REAL,
    source TEXT,
    job_id INTEGER,
    is_primary INTEGER DEFAULT 0,
    created_at TEXT,
    FOREIGN KEY(question_id) REFERENCES questions(id),
    FOREIGN KEY(lecture_id) REFERENCES lectures(id),
    FOREIGN KEY(chunk_id) REFERENCES lecture_chunks(id),
    FOREIGN KEY(material_id) REFERENCES lecture_materials(id),
    FOREIGN KEY(job_id) REFERENCES classification_jobs(id)
);

CREATE INDEX idx_question_chunk_matches_question
    ON question_chunk_matches (question_id);
CREATE INDEX idx_question_chunk_matches_lecture
    ON question_chunk_matches (lecture_id);
CREATE INDEX idx_question_chunk_matches_chunk
    ON question_chunk_matches (chunk_id);
CREATE INDEX idx_question_chunk_matches_job
    ON question_chunk_matches (job_id);
