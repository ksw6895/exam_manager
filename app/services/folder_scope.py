from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy import text

from app import db
from app.models import BlockFolder, Lecture


def parse_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def resolve_folder_ids(
    folder_id: Optional[int],
    include_descendants: bool,
    block_id: Optional[int] = None,
) -> List[int]:
    if not folder_id:
        return []
    if not include_descendants:
        return [folder_id]

    anchor_filter = ""
    recursive_filter = ""
    params: Dict[str, Any] = {"folder_id": folder_id}
    if block_id is not None:
        anchor_filter = " AND block_id = :block_id"
        recursive_filter = " WHERE bf.block_id = :block_id"
        params["block_id"] = block_id

    sql = text(
        """
        WITH RECURSIVE folder_tree(id) AS (
            SELECT id FROM block_folders WHERE id = :folder_id{anchor_filter}
            UNION ALL
            SELECT bf.id FROM block_folders bf
            JOIN folder_tree ft ON bf.parent_id = ft.id{recursive_filter}
        )
        SELECT id FROM folder_tree
        """.format(anchor_filter=anchor_filter, recursive_filter=recursive_filter)
    )
    return [row[0] for row in db.session.execute(sql, params).fetchall()]


def resolve_lecture_ids(
    block_id: Optional[int],
    folder_id: Optional[int],
    include_descendants: bool,
) -> Optional[List[int]]:
    if block_id is None and folder_id is None:
        return None

    query = Lecture.query
    if block_id is not None:
        query = query.filter(Lecture.block_id == block_id)

    if folder_id:
        folder_ids = resolve_folder_ids(folder_id, include_descendants, block_id)
        if not folder_ids:
            return []
        query = query.filter(Lecture.folder_id.in_(folder_ids))

    return [lecture.id for lecture in query.all()]


def build_folder_tree(block_id: int) -> List[Dict[str, Any]]:
    folders = (
        BlockFolder.query.filter_by(block_id=block_id)
        .order_by(BlockFolder.order, BlockFolder.id)
        .all()
    )

    nodes: Dict[int, Dict[str, Any]] = {}
    for folder in folders:
        nodes[folder.id] = {
            "id": folder.id,
            "blockId": folder.block_id,
            "parentId": folder.parent_id,
            "name": folder.name,
            "order": folder.order,
            "description": folder.description,
            "children": [],
        }

    roots: List[Dict[str, Any]] = []
    for folder in folders:
        node = nodes[folder.id]
        if folder.parent_id and folder.parent_id in nodes:
            nodes[folder.parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots
