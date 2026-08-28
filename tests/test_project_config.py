from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_actions_has_weekday_utc_schedule_manual_dispatch_tests_commit_and_pages():
    workflow = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
    assert "45 5-11 * * 1-5" in workflow
    assert "workflow_dispatch:" in workflow
    assert "deploy_only:" in workflow
    assert "inputs.deploy_only != true" in workflow
    assert "python -m pytest" in workflow
    assert "python -m holo_arxiv" in workflow
    assert "python -m holo_arxiv.time_gate" in workflow
    assert "steps.time_gate.outputs.allowed == 'true'" in workflow
    assert "python -m holo_arxiv.size_guard" in workflow
    assert "git diff --cached --quiet" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v3" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "contents: write" in workflow and "pages: write" in workflow and "id-token: write" in workflow
    assert "PUSHPLUS_ENABLED: ${{ vars.PUSHPLUS_ENABLED || 'false' }}" in workflow
    assert "git add docs data" in workflow
    assert "push:" not in workflow


def test_example_env_documents_models_urls_and_no_real_secrets():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DEEPSEEK_MODEL=deepseek-v4-flash" in env
    assert "DEEPSEEK_REVIEW_MODEL=deepseek-v4-pro" in env
    assert "DEEPSEEK_BASE_URL=https://api.deepseek.com" in env
    assert "PUSHPLUS_TOKEN=" in env
    assert "PUSHPLUS_ACCESS_KEY=" in env
    assert "PUSHPLUS_ENABLED=false" in env
    assert "SITE_BASE_URL=" in env


def test_chinese_readme_explains_offline_dry_run_and_github_secrets():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "电脑关机" in readme
    assert "python -m holo_arxiv --dry-run" in readme
    assert "DEEPSEEK_API_KEY" in readme and "PUSHPLUS_TOKEN" in readme
    assert "不要提交" in readme
