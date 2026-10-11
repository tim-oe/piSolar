"""Serialize ORM rows for JSON-lines spool envelopes."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.types import TypeDecorator

_OFFSET_RE = re.compile(r"T\d{2}:\d{2}:\d{2}(\.\d+)?-")


def _concrete_type(col_type):
    current = col_type
    seen: set[int] = set()
    while isinstance(current, TypeDecorator) and id(current) not in seen:
        seen.add(id(current))
        current = current.impl
    return current


def _encode_datetime(value: datetime) -> str:
    if value.tzinfo is not None:
        raise ValueError("datetime must be naive")
    return value.isoformat()


def _decode_datetime(value) -> datetime:
    if (
        not isinstance(value, str)
        or value.endswith("Z")
        or "+" in value
        or _OFFSET_RE.search(value)
    ):
        raise ValueError("offset-bearing datetime")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("offset-bearing datetime")
    return parsed


def _decode_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("integer value must be int")
    return int(value)


def _decode_float(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("float value must be number")
    return float(value)


_ENCODERS = (
    (DateTime, _encode_datetime),
    (Integer, int),
    (Float, float),
    (String, str),
)

_DECODERS = (
    (DateTime, _decode_datetime),
    (Integer, _decode_int),
    (Float, _decode_float),
    (String, str),
)


def _dispatch(handlers, col_type, value):
    concrete = _concrete_type(col_type)
    for type_cls, handler in handlers:
        if isinstance(concrete, type_cls):
            return handler(value)
    return value


def encode_value(col_type, value):
    if value is None:
        return None
    return _dispatch(_ENCODERS, col_type, value)


def decode_value(col_type, value):
    if value is None:
        return None
    return _dispatch(_DECODERS, col_type, value)


class RecordCodec:
    """Mapper-driven encode/decode for spooled ORM rows."""

    @staticmethod
    def encode(record) -> dict:
        data = {}
        for column in type(record).__table__.columns:
            if column.name == "id":
                continue
            data[column.name] = encode_value(column.type, getattr(record, column.name))
        return data

    @staticmethod
    def decode(record_cls, data: dict):
        record = record_cls()
        for column in record_cls.__table__.columns:
            if column.name == "id" or column.name not in data:
                continue
            setattr(
                record,
                column.name,
                decode_value(column.type, data[column.name]),
            )
        return record
