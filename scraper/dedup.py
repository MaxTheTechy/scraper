"""Cross-site duplicate detection.

The `source_url` UNIQUE constraint (scraper/worker.py) only stops the exact
same URL from being scraped twice. It says nothing about the same recipe
turning up at a different URL, or republished on a second site -- that's
what this module is for.

Two passes, both against non-duplicate rows only (status != "duplicate", so
a flagged duplicate never becomes the canonical match for a later one --
duplicate_of_id always points at an original):

1. Exact: content_hash (md5 of the normalized title) equality. Cheap, and
   catches verbatim reposts / re-scrapes-under-a-new-URL outright.
2. Fuzzy: pg_trgm word_similarity() (NOT plain similarity()) above
   TITLE_SIMILARITY_THRESHOLD, AND ingredient-name Jaccard overlap above
   INGREDIENT_OVERLAP_THRESHOLD against that same candidate. word_similarity
   matches a shorter title against its best-matching substring of a longer
   one, which plain similarity() badly under-scores (verified live: a site
   whose titles carry a long marketing suffix, e.g. "Spinach Soup - the
   Recipe That Turns a Simple Dish Into a Delight", scored 0.23 similarity
   against the plain "Spinach Soup" but 0.68 word_similarity). Since either
   the incoming or the existing title could be the longer one, both
   directions are checked and the max is taken. Requiring the ingredient
   overlap too keeps generic titles ("Chocolate Chip Cookies") from
   false-matching two genuinely different recipes.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.models.recipe import Recipe

TITLE_SIMILARITY_THRESHOLD = 0.5
INGREDIENT_OVERLAP_THRESHOLD = 0.4

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def content_hash(title: str) -> str:
    return hashlib.md5(normalize_title(title).encode("utf-8")).hexdigest()


def _normalized_ingredient_set(names: list[str]) -> set[str]:
    return {normalize_title(name) for name in names if name}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def find_duplicate(db: Session, title: str, ingredient_names: list[str]) -> Recipe | None:
    """Return the existing canonical Recipe this looks like a duplicate of,
    or None if it looks new."""
    if not title:
        return None

    canonical = Recipe.status != "duplicate"

    exact_hash = content_hash(title)
    exact_match = db.execute(
        select(Recipe).where(Recipe.content_hash == exact_hash, canonical).limit(1)
    ).scalar_one_or_none()
    if exact_match is not None:
        return exact_match

    lowered_title = title.lower()
    best_similarity = func.greatest(
        func.word_similarity(lowered_title, func.lower(Recipe.title)),
        func.word_similarity(func.lower(Recipe.title), lowered_title),
    )
    candidate = db.execute(
        select(Recipe)
        .where(canonical, best_similarity > TITLE_SIMILARITY_THRESHOLD)
        .order_by(best_similarity.desc())
        .limit(1)
    ).scalar_one_or_none()
    if candidate is None:
        return None

    incoming_ingredients = _normalized_ingredient_set(ingredient_names)
    candidate_ingredients = _normalized_ingredient_set([i.name for i in candidate.ingredients])
    if _jaccard(incoming_ingredients, candidate_ingredients) > INGREDIENT_OVERLAP_THRESHOLD:
        return candidate

    return None
