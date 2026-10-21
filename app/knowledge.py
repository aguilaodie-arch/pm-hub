import chromadb
from .config import settings

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_dir)
        _collection = _client.get_or_create_collection("knowledge")
    return _collection


def upsert_entry(entry_id, project_id, sprint_id, req_no, title, chunks, embeddings):
    """把一条知识条目的切片写入向量库（D19：条目级自包含文档）。"""
    col = _get_collection()
    ids = [f"e{entry_id}_{i}" for i in range(len(chunks))]
    metas = [
        {
            "entry_id": int(entry_id),
            "project_id": int(project_id),
            "sprint_id": int(sprint_id),
            "req_no": req_no or "",
            "title": title or "",
        }
        for _ in chunks
    ]
    col.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metas)


def delete_entry(entry_id):
    """删除单条知识条目的全部向量切片（编辑/重新归档前调用）。"""
    col = _get_collection()
    try:
        col.delete(where={"entry_id": int(entry_id)})
    except Exception:
        pass


def query_knowledge(project_id, question_vec, n=None, with_meta=False):
    """检索该项目知识库中最相关的片段。n 缺省读配置 knowledge.top_k（D20）；
    with_meta=True 时返回 (文档, 元数据) 列表。"""
    if n is None:
        try:
            n = int(settings.knowledge.get("top_k", 5))
        except (TypeError, ValueError):
            n = 5
        n = max(1, min(n, 20))
    col = _get_collection()
    try:
        res = col.query(
            query_embeddings=[question_vec],
            n_results=n,
            where={"project_id": int(project_id)},
        )
    except Exception:
        return []
    docs = (res.get("documents") or [[]])[0]
    if not with_meta:
        return docs
    metas = (res.get("metadatas") or [[]])[0]
    return list(zip(docs, metas))
