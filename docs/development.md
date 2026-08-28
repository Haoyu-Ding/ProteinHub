# ProteinHub 开发技术规范

本文档定义 ProteinHub 日常开发中的技术规则。

## 运行环境

- Python 3.11 或更高版本。
- FastAPI 用于 HTTP APIs。
- NiceGUI 用于本地 Web UI。
- SQLite 用于本地开发和测试。
- PostgreSQL 用于服务器部署。
- Artifact bytes 和 protein structure bytes 可以存入数据库；本地开发默认仍用文件系统。
- Experiment raw files 直接存入数据库。

## 安装和启动

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python main.py
```

运行测试：

```bash
.venv/bin/python -m pytest
```

运行语法检查：

```bash
.venv/bin/python -m compileall -q proteinhub tests main.py
```

## 配置

配置位于 `proteinhub/config.py`，应通过 `get_settings()` 读取。

环境变量：

- `PROTEINHUB_DATA_DIR`
- `PROTEINHUB_STORAGE_DIR`
- `PROTEINHUB_DATABASE`
- `PROTEINHUB_DATABASE_URL`
- `PROTEINHUB_ARTIFACT_STORAGE_BACKEND`
- `PROTEINHUB_JWT_SECRET`
- `PROTEINHUB_NICEGUI_STORAGE_SECRET`
- `PROTEINHUB_ADMIN_EMAILS`
- `PROTEINHUB_PUBLIC_BASE_URL`
- `PROTEINHUB_LEGACY_DOMESTICATOR_PYTHON`
- `PROTEINHUB_LEGACY_DOMESTICATOR_SCRIPT`
- `PROTEINHUB_LEGACY_DOMESTICATOR_DATABASE`
- `PROTEINHUB_LEGACY_DOMESTICATOR_TIMEOUT_SECONDS`
- `PROTEINHUB_AKTA_HAP_PYTHON`
- `PROTEINHUB_AKTA_HAP_SCRIPT`
- `PROTEINHUB_AKTA_HAP_TIMEOUT_SECONDS`

不要在配置默认值之外硬编码 secrets。默认值只适用于本地开发。

`PROTEINHUB_DATABASE_URL` 设置后使用 PostgreSQL，例如：

```bash
export PROTEINHUB_DATABASE_URL=postgresql://proteinhub:password@localhost:5432/proteinhub
```

`PROTEINHUB_ARTIFACT_STORAGE_BACKEND` 可选值为 `database` 或 `filesystem`。
当配置 PostgreSQL 且未显式设置该变量时，默认使用 `database`，也就是把
artifact bytes 和 protein structure bytes 直接存入 PostgreSQL。
Experiment raw files 不走 filesystem backend，始终保存原始 bytes 到数据库。

## API 规范

- request 和 response models 放在 `proteinhub/api/schemas.py`。
- route handlers 保持薄。
- 使用 FastAPI dependencies 管理 request-scoped dependencies，例如 DB connection 和 current user。
- route handlers 可以捕获 `DomainError`，并通过共享 API helper 映射到 HTTP。
- 不要在 route handlers 中写 SQL。
- 除非是纯 HTTP 层面的规则，否则不要在 route handlers 中直接实现权限策略。

## Application Service 规范

- 业务工作流放在 `proteinhub/application/`。
- 函数命名应面向用例，例如 `create_project`、`create_protein` 或 `soft_delete_artifact`。
- 权限检查应靠近对应用例。
- 当一个用例会修改多条记录，或同时组合数据库和文件操作时，transaction 应放在 application-service 层。
- 对预期内的产品失败抛出 domain errors。
- 避免 import FastAPI、NiceGUI 或浏览器代码。

## Repository 规范

- 数据库入口放在 `proteinhub/infrastructure/database/`。
- SQLite schema 和 repository 查询放在 `proteinhub/infrastructure/sqlite/`。
- PostgreSQL connection 和 schema setup 放在 `proteinhub/infrastructure/postgres/`。
- 只使用参数化 SQL。
- 在引入 typed models 前，数据库行可以继续以 dictionaries 返回。
- Repositories 聚焦数据访问，不承载产品策略。
- 当查询量或 schema 变化需要时，再添加 indexes 和 migrations。

## Storage 规范

- Storage adapter 放在 `proteinhub/infrastructure/storage/`。
- 文件系统 backend 只能存储在配置的 storage root 下。
- 数据库 backend 仍应保存相对路径 metadata，bytes 存在对应 BLOB/BYTEA 字段。
- Experiment raw files 使用 `experiment_raw_files.content` 保存原始 bytes，
  普通 list/detail response 只能返回 metadata。
- 所有用户提供的 filename 在路径构造前必须 sanitize。
- 对外提供文件前，必须使用 `resolve_storage_path` 或 `LocalFileStore.resolve`。
  数据库 backend 下载时必须经过授权检查后读取 bytes。

## UI 规范

- NiceGUI 页面和浏览器 helper 放在 `proteinhub/ui/`。
- `proteinhub/ui/pages.py` 负责页面注册和页面级交互；`proteinhub/ui/support.py` 放共享展示 helper 和浏览器脚本。
- UI 交互必须调用 `/api/...`。
- UI 代码不能 import database、repository、security 或 application service 模块。
- UI 页面可以通过现有 helper 把 browser token 存入 local storage。
- UI 错误处理应面向用户，保持简洁。

## 安全规范

- 密码必须通过 `hash_password` 哈希。
- 密码校验必须通过 `verify_password` 使用常量时间比较。
- JWT 创建和解码必须留在 `proteinhub/security.py`。
- Project membership 是项目数据的授权边界。
- Artifact download 必须验证授权；filesystem backend 还必须验证 storage-root containment。

## 测试规范

每次行为变更都应保持现有测试通过。

修改以下内容时，应添加或更新测试：

- permissions
- authentication
- artifact upload、download、deletion 或 path handling
- batch membership、experiment type、well mapping 或 result update
- schema shape
- API response behavior
- protein sequence normalization

推荐测试命令：

```bash
.venv/bin/python -m pytest
```

结构性重构时，也运行：

```bash
.venv/bin/python -m compileall -q proteinhub tests main.py
```

## Git Workflow

- 功能开发应使用分支。
- 偏好小 commit，并保持测试通过。
- 不要提交 `.venv/`、caches、本地数据库或 storage 文件。
- 开 PR 前运行测试，并附上简短的行为变更说明。

## Review Checklist

- 这个变更是否保持了层级边界？
- UI 是否仍然通过 API？
- 权限检查是否仍然以 project 为边界？
- SQL 查询是否参数化？
- Artifact path 是否仍然无法逃出 storage root？
- 测试是否覆盖了变化的行为？
- 配置或 secrets 是否避免了硬编码 runtime paths？
