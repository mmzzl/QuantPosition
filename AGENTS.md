<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
specs/005-sector-heatmap/plan.md

## Current Feature
- **Branch**: 005-sector-heatmap
- **Feature**: 板块热力图
- **Spec**: specs/005-sector-heatmap/spec.md

## 实盘交易同步 API

### 获取 Token
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
# 返回: {"access_token":"eyJ...","token_type":"bearer","user_id":"...","role":"super_admin"}
```

### 买入同步
```bash
curl -X POST http://localhost:8000/holdings/{user_id} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"code": "000001", "name": "平安银行", "quantity": 1000, "average_cost": 11.50}'
```

### 卖出同步
```bash
curl -X POST http://localhost:8000/holdings/{user_id}/{code}/sell \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"quantity": 500, "price": 12.00}'
```

## 技术栈
- Python 3.12 + FastAPI
- MongoDB (pymongo)
- JWT认证 (python-jose)
- 密码加密 (passlib/bcrypt)
- Vue 3 + Element Plus
- Apache ECharts (K线图)
## Nginx 管理
```bash
# 安装为 Windows 服务并启动
powershell -File scripts/nginx-service.ps1 install

# 启动/停止/重启/状态
powershell -File scripts/nginx-service.ps1 start
powershell -File scripts/nginx-service.ps1 stop
powershell -File scripts/nginx-service.ps1 restart
powershell -File scripts/nginx-service.ps1 status

# 卸载服务
powershell -File scripts/nginx-service.ps1 remove
```
nginx 路径: `C:\nginx-1.30.3\`，配置文件: `C:\nginx-1.30.3\conf\nginx.conf`

### 约束
- 先想清楚再写
- 不明白的先问
- 设计大于实践，方向错了，后面再怎么努力也没用
- 日志一定要记录清楚，日志用logging记录
<!-- SPECKIT END -->

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
