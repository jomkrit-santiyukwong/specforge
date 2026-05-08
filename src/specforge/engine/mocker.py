from __future__ import annotations

import logging
import math
import random
from collections.abc import Iterator
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from faker import Faker
except ImportError:
    class Faker:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self._random = random.Random()

        def seed_instance(self, seed: int) -> None:
            self._random.seed(seed)

        def email(self) -> str:
            return f"user{self._random.randint(1000, 9999)}@example.com"

        def date(self) -> str:
            year = self._random.randint(2000, 2030)
            month = self._random.randint(1, 12)
            day = self._random.randint(1, 28)
            return f"{year:04d}-{month:02d}-{day:02d}"

        def date_time(self) -> datetime:
            return datetime(
                self._random.randint(2000, 2030),
                self._random.randint(1, 12),
                self._random.randint(1, 28),
                self._random.randint(0, 23),
                self._random.randint(0, 59),
                self._random.randint(0, 59),
            )

        def name(self) -> str:
            first = ["Alex", "Jordan", "Taylor", "Morgan", "Casey"]
            last = ["Smith", "Lee", "Brown", "Patel", "Garcia"]
            return f"{self._random.choice(first)} {self._random.choice(last)}"

        def word(self) -> str:
            words = ["alpha", "bravo", "charlie", "delta", "echo"]
            return self._random.choice(words)

from specforge.models.spec import FieldSpec, SpecFile

_MAX_DEPTH = 20
_MAX_ARRAY_ITEMS = 1_000


def _count_distinct(values: list[Any]) -> int:
    try:
        return len(set(values))
    except TypeError:
        seen: list[Any] = []
        for value in values:
            if not any(value == existing for existing in seen):
                seen.append(value)
        return len(seen)


class MockGenerator:
    def __init__(self, seed: int | None = None) -> None:
        self._faker = Faker()
        self._random = random.Random(seed)
        if seed is not None:
            self._faker.seed_instance(seed)

    def generate(self, spec: SpecFile, mode: str) -> dict[str, Any]:
        return self._generate_object(spec.fields, mode)

    def generate_many(self, spec: SpecFile, mode: str, count: int) -> list[dict[str, Any]]:
        return list(self.iter_generate(spec, mode, count))

    def iter_generate(
        self, spec: SpecFile, mode: str, count: int
    ) -> Iterator[dict[str, Any]]:
        for _ in range(count):
            yield self.generate(spec, mode)

    def _generate_object(
        self, fields: dict[str, FieldSpec], mode: str, depth: int = 0
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for name, field_spec in fields.items():
            if mode == "minimal" and not field_spec.required:
                continue
            payload[name] = self._generate_field(field_spec, mode, name, depth + 1)
        return payload

    def _generate_field(self, field_spec: FieldSpec, mode: str, field_name: str, depth: int) -> Any:
        if depth > _MAX_DEPTH:
            if field_spec.type == "null":
                return None
            if field_spec.type == "string":
                return ""
            if field_spec.type == "number":
                return 0.0
            if field_spec.type == "integer":
                return 0
            if field_spec.type == "boolean":
                return False
            if field_spec.type == "array":
                return []
            if field_spec.type == "object":
                return {}
            return None

        if mode in {"minimal", "full"} and field_spec.default is not None:
            return field_spec.default

        if mode == "edge" and field_spec.nullable:
            return None

        if field_spec.enum:
            valid_enum = [
                v for v in field_spec.enum
                if v is not None or field_spec.nullable
            ]
            if not valid_enum:
                logger.warning(
                    "field '%s': enum has no non-null values but field is not nullable — returning type default",
                    field_name,
                )
                type_defaults = {
                    "string": "",
                    "number": 0.0,
                    "integer": 0,
                    "boolean": False,
                    "array": [],
                    "object": {},
                }
                return type_defaults.get(field_spec.type, None)
            if mode in {"minimal", "edge"}:
                return valid_enum[0]
            return self._random.choice(valid_enum)

        if field_spec.type == "null":
            return None
        if field_spec.type == "string":
            return self._gen_string(field_spec, mode, field_name)
        if field_spec.type == "number":
            return self._gen_number(field_spec, mode)
        if field_spec.type == "integer":
            return self._gen_integer(field_spec, mode)
        if field_spec.type == "boolean":
            return self._gen_boolean(mode)
        if field_spec.type == "array":
            return self._gen_array(field_spec, mode, depth)
        if field_spec.type == "object":
            return self._generate_object(field_spec.fields or {}, mode, depth)
        return None

    def _gen_string(self, field_spec: FieldSpec, mode: str, field_name: str) -> str:
        if field_spec.pattern is not None:
            logger.warning(
                "field '%s': pattern constraint skipped during mock generation",
                field_name,
            )

        if mode == "edge":
            if field_spec.format == "email":
                return "a@b.co"
            if field_spec.format == "date":
                return "2000-01-01"
            if field_spec.format == "date-time":
                return "2000-01-01T00:00:00"
            target = field_spec.minLength if field_spec.minLength is not None else 0
            if field_spec.maxLength is not None:
                target = min(target, field_spec.maxLength)
            return "x" * max(target, 0)

        if field_spec.format in ("email", "date", "date-time") or "email" in field_name.lower() or "name" in field_name.lower():
            value = self._example_string(field_spec, field_name)
        else:
            base = field_name or "value"
            value = f"{base}_{self._random.randint(1000, 9999)}"

        return self._fit_string(value, field_spec)

    def _gen_number(self, field_spec: FieldSpec, mode: str) -> float:
        if mode == "edge":
            return float(field_spec.minimum if field_spec.minimum is not None else 0)

        minimum = field_spec.minimum if field_spec.minimum is not None else 0.0
        maximum = field_spec.maximum if field_spec.maximum is not None else minimum + 100.0
        if maximum < minimum:
            maximum = minimum
        if minimum == maximum:
            return float(minimum)
        value = round(self._random.uniform(minimum, maximum), 2)
        return min(max(value, minimum), maximum)

    def _gen_integer(self, field_spec: FieldSpec, mode: str) -> int:
        if mode == "edge":
            if field_spec.minimum is not None:
                return math.ceil(field_spec.minimum)
            return 0

        minimum = math.ceil(field_spec.minimum) if field_spec.minimum is not None else 0
        maximum = math.floor(field_spec.maximum) if field_spec.maximum is not None else minimum + 100
        if maximum < minimum:
            maximum = minimum
        return self._random.randint(minimum, maximum)

    def _gen_boolean(self, mode: str) -> bool:
        if mode == "edge":
            return False
        return self._random.choice([True, False])

    def _gen_array(self, field_spec: FieldSpec, mode: str, depth: int) -> list[Any]:
        if depth > _MAX_DEPTH:
            return []

        if mode == "edge":
            count = field_spec.minItems if field_spec.minItems is not None else 0
        elif mode == "minimal":
            count = field_spec.minItems if field_spec.minItems is not None else 1
        else:
            minimum = field_spec.minItems if field_spec.minItems is not None else 1
            maximum = field_spec.maxItems if field_spec.maxItems is not None else max(minimum, 3)
            if maximum < minimum:
                maximum = minimum
            count = self._random.randint(minimum, maximum)

        count = min(count, _MAX_ARRAY_ITEMS)

        if field_spec.items is None:
            if count > 0:
                logger.warning(
                    "array field has minItems=%d but no items spec — generating empty array",
                    count,
                )
            return []

        if not field_spec.uniqueItems:
            return [
                self._generate_field(field_spec.items, mode, "item", depth + 1)
                for _ in range(count)
            ]

        max_distinct: int | None = None
        if field_spec.items.enum is not None:
            max_distinct = _count_distinct(field_spec.items.enum)
        elif field_spec.items.type == "boolean":
            max_distinct = 2

        if max_distinct is not None and count > max_distinct:
            min_required = field_spec.minItems if field_spec.minItems is not None else 0
            if max_distinct < min_required:
                logger.warning(
                    "uniqueItems with minItems=%d but only %d distinct value(s) available — "
                    "emitting array with %d item(s), which violates minItems",
                    min_required,
                    max_distinct,
                    max_distinct,
                )
            count = max_distinct

        unique_items: list[Any] = []
        seen_hashable: set[Any] = set()
        unhashable_mode = False
        attempts = 0
        max_attempts = max(count * 10, 50)
        while len(unique_items) < count and attempts < max_attempts:
            attempts += 1
            value = self._generate_field(field_spec.items, mode, "item", depth + 1)
            if unhashable_mode:
                if not any(value == existing for existing in unique_items):
                    unique_items.append(value)
            else:
                try:
                    if value in seen_hashable:
                        continue
                    seen_hashable.add(value)
                    unique_items.append(value)
                except TypeError:
                    unhashable_mode = True
                    if not any(value == existing for existing in unique_items):
                        unique_items.append(value)
        return unique_items

    def _example_string(self, field_spec: FieldSpec, field_name: str) -> str:
        if field_spec.format == "email":
            value = self._faker.email()
        elif field_spec.format == "date":
            value = self._faker.date()
        elif field_spec.format == "date-time":
            value = datetime.isoformat(self._faker.date_time())
        elif "name" in field_name.lower():
            value = self._faker.name()
        elif "email" in field_name.lower():
            value = self._faker.email()
        else:
            value = self._faker.word()
        return self._fit_string(value, field_spec)

    def _fit_string(self, value: str, field_spec: FieldSpec) -> str:
        minimum = field_spec.minLength if field_spec.minLength is not None else 0
        maximum = field_spec.maxLength

        # if format is set, check compatibility before enforcing
        if field_spec.format in ('email', 'date', 'date-time'):
            length_ok = (len(value) >= minimum) and (maximum is None or len(value) <= maximum)
            if not length_ok:
                logger.warning(
                    "format '%s' value length %d is incompatible with minLength=%s, maxLength=%s — emitting format value as-is",
                    field_spec.format,
                    len(value),
                    field_spec.minLength,
                    field_spec.maxLength,
                )
            return value  # always return format value unchanged

        if maximum is not None and len(value) > maximum:
            value = value[:maximum]
        if len(value) < minimum:
            value = value + ('x' * (minimum - len(value)))

        return value
