def test_monitoring_gap_model_importable():
    from app.models.monitoring_gap import MonitoringGap
    assert MonitoringGap.__tablename__ == "monitoring_gaps"
