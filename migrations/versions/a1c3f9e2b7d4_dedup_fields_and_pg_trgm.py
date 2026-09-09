"""dedup fields (content_hash, duplicate_of_id) + pg_trgm

Revision ID: a1c3f9e2b7d4
Revises: 0e7d98a927f9
Create Date: 2026-09-09 00:00:00.000000

"""
import hashlib
import re
import unicodedata
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c3f9e2b7d4'
down_revision: Union[str, Sequence[str], None] = '0e7d98a927f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    """Mirrors scraper/dedup.py::normalize_title -- duplicated here so this
    migration doesn't depend on app code shape at future migration time."""
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _content_hash(title: str) -> str:
    return hashlib.md5(_normalize_title(title).encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column('recipes', sa.Column('content_hash', sa.String(), nullable=True))
    op.add_column('recipes', sa.Column('duplicate_of_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_recipes_duplicate_of_id_recipes', 'recipes', 'recipes',
        ['duplicate_of_id'], ['id'],
    )
    op.create_index('ix_recipes_content_hash', 'recipes', ['content_hash'])
    op.execute(
        "CREATE INDEX ix_recipes_title_trgm ON recipes "
        "USING gin (lower(title) gin_trgm_ops)"
    )

    # Backfill content_hash for existing rows so new scrapes get compared
    # against them too (see scraper/dedup.py).
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, title FROM recipes")).fetchall()
    for row_id, title in rows:
        if not title:
            continue
        connection.execute(
            sa.text("UPDATE recipes SET content_hash = :hash WHERE id = :id"),
            {"hash": _content_hash(title), "id": row_id},
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_recipes_title_trgm")
    op.drop_index('ix_recipes_content_hash', table_name='recipes')
    op.drop_constraint('fk_recipes_duplicate_of_id_recipes', 'recipes', type_='foreignkey')
    op.drop_column('recipes', 'duplicate_of_id')
    op.drop_column('recipes', 'content_hash')
