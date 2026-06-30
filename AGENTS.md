# ProteinHub Agent 指南

修改 ProteinHub 时，请遵守下面这些项目规则。

## 命令

代码变更后使用这些验证命令：

```bash
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q proteinhub tests main.py
```

## 架构

遵守下面的依赖方向：

```text
ui -> api -> application -> infrastructure
              |
              v
            domain
```

`app.py` 是组合根，可以装配所有层。

兼容模块 `proteinhub.db`、`proteinhub.storage` 和 `proteinhub.services` 是 legacy exports。新的内部代码应从 canonical layered modules import。

## 硬性规则

- UI 必须调用 `/api/...`；不要让 UI import database、security、repositories 或 application services。
- API routes 必须保持薄，不能包含 SQL。
- 业务规则和权限属于 `proteinhub/application/`。
- SQLite 查询属于 `proteinhub/infrastructure/sqlite/`。
- 文件路径构造和 artifact bytes 存储属于 `proteinhub/infrastructure/storage/`。
- Domain errors 属于 `proteinhub/domain/errors.py`。

## 安全 Review 重点

重点关注：

- project membership checks
- owner-only actions
- artifact download authorization
- storage path traversal prevention
- JWT validation
- password hashing and verification

## 测试预期

修改以下内容时，应添加或更新测试：

- auth
- project permissions
- artifact upload/download/delete
- storage path handling
- API response shape
- sequence normalization

如果没有运行测试，必须说明。

