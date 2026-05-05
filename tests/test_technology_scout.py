from tradingagents.company import (
    build_technology_capabilities,
    render_technology_scout_report,
)


def test_technology_scout_reports_core_capabilities(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / ".agents" / "skills").mkdir(parents=True)

    capabilities = build_technology_capabilities(
        project_root=tmp_path,
        ollama_base_url="http://127.0.0.1:9",
    )
    names = {capability.name for capability in capabilities}

    assert "TradingAgents upstream architecture" in names
    assert "Backtrader" in names
    assert "Repo knowledge and skills" in names

    report = render_technology_scout_report(capabilities)
    assert "# Technology Scout Report" in report
    assert "Capability Matrix" in report
    assert "knowledge+skills present" in report
