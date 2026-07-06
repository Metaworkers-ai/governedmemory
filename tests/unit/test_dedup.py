from core.write_governor import normalize, find_duplicate


class TestNormalize:
    def test_strips_and_lowercases(self):
        assert normalize("  Hello World  ") == "hello world"

    def test_collapses_internal_whitespace(self):
        assert normalize("Hello    World\n\tfoo") == "hello world foo"

    def test_identical_after_normalization(self):
        assert normalize("Customer prefers  EMAIL.") == normalize("customer prefers email.")


class TestFindDuplicate:
    def test_no_existing_records_returns_none(self):
        assert find_duplicate([], "some content") is None

    def test_exact_match_returns_row(self):
        existing = [{"id": "a1", "content": "Customer prefers email contact.", "superseded_by": None}]
        result = find_duplicate(existing, "Customer prefers email contact.")
        assert result is not None
        assert result["id"] == "a1"

    def test_match_is_case_and_whitespace_insensitive(self):
        existing = [{"id": "a1", "content": "Customer   prefers EMAIL contact.", "superseded_by": None}]
        result = find_duplicate(existing, "customer prefers email contact.")
        assert result is not None

    def test_different_content_returns_none(self):
        existing = [{"id": "a1", "content": "Customer prefers email contact.", "superseded_by": None}]
        assert find_duplicate(existing, "Customer prefers phone contact.") is None

    def test_already_superseded_row_is_ignored(self):
        existing = [{"id": "a1", "content": "Customer prefers email contact.", "superseded_by": "b2"}]
        assert find_duplicate(existing, "Customer prefers email contact.") is None

    def test_returns_most_recent_when_multiple_present(self):
        # caller is expected to pass newest-first; find_duplicate returns the first match
        existing = [
            {"id": "newest", "content": "Customer prefers email contact.", "superseded_by": None},
            {"id": "older", "content": "Customer prefers email contact.", "superseded_by": None},
        ]
        result = find_duplicate(existing, "Customer prefers email contact.")
        assert result["id"] == "newest"
