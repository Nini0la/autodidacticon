from collections import defaultdict


def test_each_concept_has_learning_and_question_units(sut, new_ulid, sample_source_text):
    ctx = sut.run_source_provided_flow(
        user_id=new_ulid(),
        session_id=new_ulid(),
        topic_title="Protein synthesis",
        source_input=sample_source_text,
    )
    concepts = ctx["concepts"]
    units = ctx["units"]

    by_concept = defaultdict(set)
    for unit in units:
        by_concept[unit["concept_id"]].add(unit["card_type"])

    for concept in concepts:
        seen = by_concept[concept["concept_id"]]
        assert "learning" in seen
        assert "question" in seen


def test_question_units_reference_paired_learning_units(sut, new_ulid, sample_source_text):
    ctx = sut.run_source_provided_flow(
        user_id=new_ulid(),
        session_id=new_ulid(),
        topic_title="Cell division",
        source_input=sample_source_text,
    )
    learning_units, question_units = ctx["learning_units"], ctx["question_units"]
    learning_by_id = {u["unit_id"]: u for u in learning_units}

    for question in question_units:
        related = question.get("related_unit_id")
        assert related in learning_by_id
        paired = learning_by_id[related]
        assert paired["topic_id"] == question["topic_id"]
        assert paired["concept_id"] == question["concept_id"]
