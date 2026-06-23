import pytest

from jfrog_mcp.app.pagination import decode_cursor, encode_cursor, paginate_sequence


def test_cursor_round_trip():
    cursor = encode_cursor(50)
    assert decode_cursor(cursor) == 50


def test_paginate_sequence_returns_next_cursor():
    page = paginate_sequence([1, 2, 3], cursor=None, limit=2)

    assert page.items == [1, 2]
    assert page.next_cursor is not None
    assert decode_cursor(page.next_cursor) == 2


def test_decode_cursor_rejects_invalid_values():
    with pytest.raises(ValueError):
        decode_cursor("not-a-cursor")
