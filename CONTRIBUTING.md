# Contribution Guidelines

感谢您对 InsightGraph 的贡献！本指南帮助您快速开始。

## 贡献方式

### 🐛 报告 Bug

发现 bug？请创建 Issue，包含：
- **问题描述**: 清晰简洁的问题说明
- **复现步骤**: 最小化复现用例
- **实际结果** vs **预期结果**
- **环境信息**: Python 版本、OS、LLM provider（如适用）
- **日志/错误**: `debug.log` 或完整堆栈跟踪

### 💡 功能建议

有新想法？请创建 Issue，标记为 `enhancement`，包含：
- **用例描述**: 解决什么问题
- **建议方案**: 如何实现（可选）
- **相关文档**: 相关架构或依赖说明

### 📝 改进文档

发现文档不清晰？直接创建 PR，修改对应的 `.md` 文件。

### 💻 贡献代码

#### 准备开发环境

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

#### 开发工作流

1. **创建 Feature Branch**
   ```bash
   git checkout -b feat/your-feature-name
   # 或修复 bug：
   git checkout -b fix/issue-123-description
   ```

2. **修改代码**
   - 遵循 [PEP 8](https://pep8.org/) 代码风格
   - 代码行长 ≤ 100 字符（ruff 配置）
   - 为新函数/类添加 docstring
   - 为复杂逻辑添加注释

3. **运行本地检查**
   ```bash
   # Lint 检查
   python -m ruff check src/insight_graph/
   python -m ruff format src/insight_graph/

   # 单元测试
   python -m pytest tests/ -v

   # 覆盖率检查
   python -m pytest tests/ --cov=src/insight_graph --cov-report=term-missing
   ```

4. **Commit & Push**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   git push origin feat/your-feature-name
   ```

   **Commit 信息规范**（遵循 Conventional Commits）：
   ```
   feat:     新功能 (feature)
   fix:      bug 修复
   docs:     文档修改
   style:    代码格式（不影响功能）
   refactor: 代码重构
   test:     测试相关
   chore:    构建/依赖更新
   ```

   示例：
   ```
   feat: add live URL validation for reporter

   - Implement Reporter.validate_urls() method
   - Add citation support metadata tracking
   - Include failed URL diagnostics in report

   Fixes #123
   ```

5. **创建 Pull Request**
   - PR 标题遵循 Conventional Commits
   - 描述修改内容、相关 Issue（使用 `Fixes #123` 或 `Closes #123`）
   - 确保 GitHub Actions 通过

#### 代码审查清单

PR 作者：
- [ ] 本地 `ruff check` 和 `ruff format` 通过
- [ ] 本地 `pytest` 全部通过
- [ ] 新增功能包含单元测试
- [ ] 更新文档（如涉及 API 变更）
- [ ] Commit 信息清晰（Conventional Commits）
- [ ] 无不必要的代码注释（代码应该自解释）

审查人员：
- 代码逻辑正确性和安全性
- 测试覆盖率（新代码应 ≥ 85%）
- 文档完整性
- 是否符合项目架构设计

## 测试指南

### 运行全部测试
```bash
python -m pytest tests/ -v
```

### 运行特定测试
```bash
python -m pytest tests/test_web_search.py -v
python -m pytest tests/test_api.py::test_research_endpoint -v
```

### 运行离线评估
```bash
insight-graph-eval --case-file docs/evals/default.json
```

### 运行 Smoke 测试（部署检验）
```bash
insight-graph-smoke --help
insight-graph-smoke
```

## 文档约定

- 用中英混合文档时，英文术语保持原文（如 LLM、evidence、provider）
- 配置示例使用环境变量名和类型（如 `INSIGHT_GRAPH_USE_WEB_SEARCH` = `1` / `true` / `yes`）
- API 文档应包含请求/响应示例
- 添加新功能时在 `CHANGELOG.md` 的 `## Unreleased` 部分添加简洁记录

## 发布流程（Maintainer Only）

1. 更新 `pyproject.toml` 版本号（遵循 Semantic Versioning）
2. 在 `CHANGELOG.md` 中添加发布日期和版本号
3. 创建 Git tag: `git tag v0.x.y`
4. 推送 tag: `git push origin v0.x.y`
5. GitHub Actions 自动构建和发布到 PyPI

## 行为准则

请阅读 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。简言之：
- 尊重他人
- 建设性反馈
- 包容多元观点

## 问题求助

- **技术问题**: GitHub Issues
- **讨论**: GitHub Discussions（如有）
- **安全漏洞**: 请勿公开发布，邮件联系维护者

感谢贡献！🎉
