from core.retrieval_engine import reciprocal_rank_fusion


class TestReciprocalRankFusion:
    def test_empty_lists_returns_empty(self):
        assert reciprocal_rank_fusion([]) == {}
        assert reciprocal_rank_fusion([[], []]) == {}

    def test_single_list_preserves_relative_order(self):
        scores = reciprocal_rank_fusion([["a", "b", "c"]])
        assert scores["a"] > scores["b"] > scores["c"]

    def test_item_in_both_lists_outranks_item_in_one(self):
        vector_ranked = ["a", "b", "c"]
        lexical_ranked = ["a", "x", "y"]
        scores = reciprocal_rank_fusion([vector_ranked, lexical_ranked])
        # "a" appears at rank 1 in both lists — should clearly beat "b",
        # which only appears once (rank 2 in one list).
        assert scores["a"] > scores["b"]
        assert scores["a"] > scores["x"]

    def test_all_ids_from_all_lists_present(self):
        scores = reciprocal_rank_fusion([["a", "b"], ["c", "d"]])
        assert set(scores.keys()) == {"a", "b", "c", "d"}

    def test_custom_k_changes_scores_but_not_ordering_within_a_list(self):
        list_a = ["a", "b", "c"]
        scores_default = reciprocal_rank_fusion([list_a])
        scores_k1 = reciprocal_rank_fusion([list_a], k=1)
        assert scores_default["a"] > scores_default["b"] > scores_default["c"]
        assert scores_k1["a"] > scores_k1["b"] > scores_k1["c"]
        assert scores_default != scores_k1
