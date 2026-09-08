"""Parser for schema.org Recipe data embedded as application/ld+json.

Not used by scraper/sites/unica.py (that site has no Recipe JSON-LD, only an
Article-type block), but kept as a real, independently-correct utility for
future sites that DO publish schema.org Recipe JSON-LD, per project spec
Section 4 / Section 8.

Handles the shapes the W3C/schema.org spec allows:
- A single JSON-LD object, a list of objects, or an object with "@graph".
- "@type" as a string or a list of strings (e.g. ["Recipe", "Article"]).
- recipeInstructions as: a plain string (optionally with newline-separated
  steps), a list of strings, a list of HowToStep objects, or a list of
  HowToSection objects each containing nested itemListElement HowToSteps.
- image as: a string URL, a dict with "url", or a list of either.
- recipeYield / servings as an int, or a string like "4 servings" / "4".
- ISO 8601 durations (PT#H#M / PT#D...) for prepTime/cookTime/totalTime.
"""

from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DURATION_RE = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?"
    r")?$"
)


def parse_iso8601_duration_to_minutes(duration: str | None) -> int | None:
    """Convert an ISO 8601 duration (e.g. "PT1H30M") to whole minutes."""
    if not duration or not isinstance(duration, str):
        return None
    match = _DURATION_RE.match(duration.strip())
    if not match:
        return None
    parts = match.groupdict()
    if all(v is None for v in parts.values()):
        return None
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = float(parts["seconds"] or 0)
    total_minutes = days * 24 * 60 + hours * 60 + minutes + seconds / 60
    return round(total_minutes)


def _first_int(value) -> int | None:
    """Best-effort extraction of a leading integer from an int/str/list
    (recipeYield can be "4", 4, "4 servings", or ["4 servings", "4"])."""
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            result = _first_int(item)
            if result is not None:
                return result
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())
    return None


def _extract_image_url(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("url")
    if isinstance(value, list) and value:
        return _extract_image_url(value[0])
    return None


def _flatten_instructions(value) -> list[str]:
    """Normalize recipeInstructions (str | list[str] | list[HowToStep] |
    list[HowToSection]) into a flat ordered list of step strings."""
    steps: list[str] = []

    if value is None:
        return steps

    if isinstance(value, str):
        # Some publishers put all steps in one string separated by newlines.
        for line in value.splitlines():
            line = line.strip()
            if line:
                steps.append(line)
        return steps

    if isinstance(value, dict):
        value = [value]

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    steps.append(text)
            elif isinstance(item, dict):
                item_type = item.get("@type", "")
                if isinstance(item_type, list):
                    item_type = " ".join(item_type)
                if "HowToSection" in item_type:
                    # Nested section: recurse into itemListElement.
                    steps.extend(_flatten_instructions(item.get("itemListElement")))
                else:
                    # HowToStep (or untyped) -- prefer "text", fall back to "name".
                    text = item.get("text") or item.get("name")
                    if text:
                        steps.append(str(text).strip())

    return steps


def _flatten_ingredients(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
        return result
    return []


def _node_types(node: dict) -> list[str]:
    node_type = node.get("@type", "")
    if isinstance(node_type, str):
        return [node_type]
    if isinstance(node_type, list):
        return [str(t) for t in node_type]
    return []


def _iter_nodes(data):
    """Yield every dict node in a JSON-LD document, unwrapping top-level
    lists and "@graph" containers."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            for item in data["@graph"]:
                yield from _iter_nodes(item)
        else:
            yield data


def _find_recipe_node(data) -> dict | None:
    for node in _iter_nodes(data):
        if "Recipe" in _node_types(node):
            return node
    return None


def extract_recipe_json_ld(html: str) -> dict | None:
    """Find and parse the first schema.org Recipe JSON-LD block in `html`.

    Returns a normalized dict (same shape produced by the per-site HTML
    parsers: title, description, prep_time, cook_time, total_time, servings,
    method, image_url, ingredients, source_url-less -- caller fills that in)
    or None if no Recipe JSON-LD block is present.
    """
    soup = BeautifulSoup(html, "html.parser")
    recipe_node = None

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.debug("skipping malformed JSON-LD block")
            continue
        recipe_node = _find_recipe_node(data)
        if recipe_node is not None:
            break

    if recipe_node is None:
        return None

    return {
        "title": recipe_node.get("name"),
        "description": recipe_node.get("description"),
        "prep_time": parse_iso8601_duration_to_minutes(recipe_node.get("prepTime")),
        "cook_time": parse_iso8601_duration_to_minutes(recipe_node.get("cookTime")),
        "total_time": parse_iso8601_duration_to_minutes(recipe_node.get("totalTime")),
        "servings": _first_int(recipe_node.get("recipeYield")),
        "cuisine": recipe_node.get("recipeCuisine"),
        "tags": (
            [t.strip() for t in recipe_node.get("keywords", "").split(",") if t.strip()]
            if isinstance(recipe_node.get("keywords"), str)
            else recipe_node.get("keywords")
            if isinstance(recipe_node.get("keywords"), list)
            else None
        ),
        "method": _flatten_instructions(recipe_node.get("recipeInstructions")),
        "image_url": _extract_image_url(recipe_node.get("image")),
        "ingredients": _flatten_ingredients(recipe_node.get("recipeIngredient")),
    }
