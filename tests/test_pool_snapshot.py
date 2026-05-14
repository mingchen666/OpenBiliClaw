from openbiliclaw.discovery.pool_snapshot import build_pool_distribution_snapshot
from openbiliclaw.storage.database import Database


def test_build_pool_snapshot_marks_saturated_topics_and_styles(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    for index in range(12):
        db.cache_content(
            f"BVai{index}",
            title=f"AI item {index}",
            topic_group="AI 编程",
            style_key="deep_dive",
            franchise_key="",
            source="search",
            relevance_score=0.8,
            pool_expression="x",
            pool_topic_label="x",
        )
    for index in range(3):
        db.cache_content(
            f"BVdoc{index}",
            title=f"doc item {index}",
            topic_group="人物纪录",
            style_key="story_doc",
            source="search",
            relevance_score=0.75,
            pool_expression="x",
            pool_topic_label="x",
        )

    snapshot = build_pool_distribution_snapshot(
        db,
        pool_target_count=60,
        source_targets={"bilibili": 48, "xiaohongshu": 6, "douyin": 6},
    )

    assert snapshot.pool_available_count == 15
    assert "AI 编程" in snapshot.saturated_topics
    assert "deep_dive" in snapshot.saturated_styles
    assert snapshot.source_deficits["bilibili"] == 33
