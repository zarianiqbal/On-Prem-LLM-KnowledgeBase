"""Integration test for the ACL-filtered retrieval — the security core.

Unlike test_basic.py, this needs a real Postgres + pgvector (the filter is SQL,
so it can't be exercised in memory). It runs inside a transaction that is always
rolled back, so it never leaves data behind, and it skips cleanly when no
database is reachable (e.g. CI without a DB service).

Embeddings are monkeypatched to a fixed, distinctive vector so the test needs no
model download and its inserted chunks rank ahead of any pre-existing rows.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import retrieval
from app.config import settings
from app.models import Chunk, Document


@pytest.fixture
def db_session():
    engine = create_engine(settings.database_url, future=True)
    try:
        conn = engine.connect()
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"No database available for integration test: {exc}")
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()  # discard everything this test inserted
        conn.close()
        engine.dispose()


def test_acl_filter_enforces_role_boundary(db_session, monkeypatch):
    # A one-hot vector that real (normalized) embeddings won't match, so our two
    # chunks sit at distance 0 and rank ahead of any leftover rows in the DB.
    vec = [1.0] + [0.0] * (settings.embedding_dim - 1)
    monkeypatch.setattr(retrieval, "embed_text", lambda _q: vec)

    hr_doc = Document(filename="acl_hr.txt", allowed_roles=["hr"], num_chunks=1)
    pub_doc = Document(filename="acl_pub.txt", allowed_roles=[], num_chunks=1)
    db_session.add_all([hr_doc, pub_doc])
    db_session.flush()
    db_session.add_all([
        Chunk(document_id=hr_doc.id, chunk_index=0, content="hr only secret",
              allowed_roles=["hr"], embedding=vec),
        Chunk(document_id=pub_doc.id, chunk_index=0, content="public info",
              allowed_roles=[], embedding=vec),
    ])
    db_session.flush()

    # An hr user sees the hr doc and the public doc.
    hr_files = {c.filename for c in retrieval.retrieve(db_session, "q", roles=["hr"])}
    assert "acl_hr.txt" in hr_files
    assert "acl_pub.txt" in hr_files

    # A customer (no roles) sees the public doc but NEVER the hr-tagged one.
    cust_files = {c.filename for c in retrieval.retrieve(db_session, "q", roles=[])}
    assert "acl_pub.txt" in cust_files
    assert "acl_hr.txt" not in cust_files

    # An admin bypasses ACL and sees the hr doc even with an unrelated role.
    admin_files = {
        c.filename
        for c in retrieval.retrieve(db_session, "q", roles=["nonsense"], is_admin=True)
    }
    assert "acl_hr.txt" in admin_files
