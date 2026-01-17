"""
Build embeddings for lecture chunks.

Usage:
  python scripts/build_embeddings.py --db data/dev.db --rebuild
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import create_app, db
from app.models import LectureChunk, LectureChunkEmbedding
from app.services.embedding_utils import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL_NAME,
    embed_texts,
    encode_embedding,
)


def _normalize_db_uri(db_value: str | None) -> str | None:
    if not db_value:
        return None
    if "://" in db_value:
        return db_value
    path = Path(db_value).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def build_embeddings(
    db_uri: str,
    model_name: str,
    dim: int,
    batch_size: int,
    rebuild: bool,
) -> None:
    app = create_app('default', db_uri_override=db_uri, skip_migration_check=True)
    with app.app_context():
        if rebuild:
            # Table uses chunk_id as PK, so multiple models cannot coexist.
            # Clear all rows on rebuild to avoid UNIQUE constraint errors.
            LectureChunkEmbedding.query.delete(synchronize_session=False)
            db.session.commit()

        existing_ids = {
            row.chunk_id
            for row in LectureChunkEmbedding.query.filter_by(model_name=model_name).all()
        }

        chunks = LectureChunk.query.order_by(LectureChunk.id).all()
        total = len(chunks)
        processed = 0

        for i in range(0, total, batch_size):
            batch = chunks[i : i + batch_size]
            texts = [chunk.content for chunk in batch]
            vectors = embed_texts(texts, model_name, dim, is_query=False)

            inserts = []
            for chunk, vec in zip(batch, vectors):
                if chunk.id in existing_ids:
                    continue
                inserts.append(
                    LectureChunkEmbedding(
                        chunk_id=chunk.id,
                        lecture_id=chunk.lecture_id,
                        model_name=model_name,
                        embedding=encode_embedding(vec),
                    )
                )

            if inserts:
                db.session.add_all(inserts)
                db.session.commit()

            processed = min(i + batch_size, total)
            print(f"Processed {processed}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build lecture chunk embeddings.")
    parser.add_argument("--db", default="data/dev.db", help="SQLite db path.")
    parser.add_argument(
        "--model", default=DEFAULT_EMBEDDING_MODEL_NAME, help="Embedding model name."
    )
    parser.add_argument(
        "--dim", type=int, default=DEFAULT_EMBEDDING_DIM, help="Embedding dimension."
    )
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    db_uri = _normalize_db_uri(args.db)
    if not db_uri:
        raise ValueError("DB path is required.")

    build_embeddings(
        db_uri,
        model_name=args.model,
        dim=args.dim,
        batch_size=args.batch_size,
        rebuild=args.rebuild,
    )


if __name__ == "__main__":
    main()
