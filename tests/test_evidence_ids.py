from paper_review_agent.evidence_ids import (
    evidence_element_id,
    format_table_cell_suffix,
    normalized_object_locator,
    table_aggregate_suffix,
)


def test_roman_and_appendix_object_labels_are_normalized_deterministically():
    assert normalized_object_locator(
        "Table IV", content_kind="table", source_element_id="elem-table"
    ) == ("table-04", "Table 4")
    assert normalized_object_locator(
        "Fig. IX", content_kind="caption", source_element_id="elem-figure"
    ) == ("figure-09", "Figure 9")
    assert normalized_object_locator(
        "Table A.1", content_kind="table", source_element_id="elem-appendix"
    ) == ("table-a-01", "Table A.1")


def test_text_retains_parser_id_and_unlabeled_visual_has_stable_object_key():
    assert evidence_element_id(
        object_label=None,
        content_kind="text",
        source_element_id="elem-text-abc",
    ) == ("elem-text-abc", None)
    first = evidence_element_id(
        object_label=None,
        content_kind="diagram",
        source_element_id="elem-diagram-abc",
    )
    second = evidence_element_id(
        object_label=None,
        content_kind="diagram",
        source_element_id="elem-diagram-abc",
    )
    assert first == second
    assert first[0].startswith("diagram-unlabeled-")


def test_cell_and_row_group_suffixes_are_human_readable_and_unambiguous():
    assert format_table_cell_suffix(3, 4) == "cell-r03-c04"
    assert format_table_cell_suffix(103, 4) == "cell-r103-c04"
    assert table_aggregate_suffix(
        chunk_text="short group",
        span_end=100,
        row_indices=[0, 12, 13, 14],
        chunk_id="abcdef0123456789",
    ) == "rows-r12-r14"
    assert table_aggregate_suffix(
        chunk_text="complete",
        span_end=8,
        row_indices=[0, 1],
        chunk_id="abcdef0123456789",
    ) == "whole"
