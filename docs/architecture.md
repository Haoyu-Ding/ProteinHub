# ProteinHub 架构规范

ProteinHub 是一个本地优先的蛋白设计工作台。应用围绕下面这个固定层级展开：

```text
Project -> Protein -> Artifact
Project -> Batch -> Experiment -> BatchWell -> Protein
```

Project 负责权限边界。Protein 是核心科研记录，并且直接携带唯一的氨基酸序列。Batch 是项目内的一次 96 孔板式蛋白集合与孔位映射。Experiment 挂在 Batch 下，目前类型为 FPLC、SPR、HPLC、AKTA；每个 Experiment 通过 BatchWell 把结果映射回对应 Protein。Artifact 用来把实验资料、分析结果和其他文件挂载到某个蛋白上。Experiment raw files 用来保存不适合直接挂到某一个 protein 的原始上传文件，以及 HPLC 这类需要复算的 per-well 输入文件。

## 架构目标

- 框架代码和业务规则分离。
- 业务规则和数据库查询、文件/bytes 写入分离。
- UI 行为必须通过公开 API 进入后端。
- 未来更换存储、数据库或处理流程时，变更应尽量局部化在某一层。
- 保持 MVP 足够轻量，同时给数据库迁移和类型化领域对象留下空间。

## 分层

```text
proteinhub/
  app.py
  config.py
  api/
  application/
  domain/
  infrastructure/
  ui/
```

### `app.py`

`app.py` 是组合根。它读取配置、初始化基础设施、创建 FastAPI 应用、注册 API 路由、安装 UI 页面，并把 NiceGUI 挂载到 FastAPI 上。

因为它的职责是装配，所以可以 import 任意层。业务规则不应该写在这里。

### `api/`

API 层负责 HTTP 相关事项：

- FastAPI routers
- request 和 response schemas
- dependency functions
- HTTP 状态码映射
- 文件响应处理

路由处理函数应保持很薄。它们负责校验和拆包 HTTP 输入，调用 application service，然后返回适合 API 的数据。

API 路由可以 import `application`、`domain`，以及响应交付所需的少量基础设施适配器，例如解析本地下载路径。

API 路由中不能写 SQL 查询，也不能直接承载业务策略。

### `application/`

Application 层负责业务用例：

- 服务器端账号创建和认证流程
- 项目成员和 owner 规则
- project、protein、artifact 用例
- batch、experiment 和 batch well 结果回填用例
- protein sequence 规范化
- artifact 上传编排

Application 代码可以协调 repository、transaction、权限检查和 file store。它应该用业务语言表达意图。

Application service 可以 import `domain` 和 `infrastructure`。

Application service 不能 import `api`、`ui`、FastAPI、NiceGUI 或浏览器相关代码。

### `domain/`

Domain 层包含不依赖框架、可在应用内共享的领域概念：

- domain errors
- 未来的 domain models
- 未来的 enum/value object，例如 role 或 artifact type

Domain 代码不应 import `api`、`application`、`infrastructure` 或 `ui`。

### `infrastructure/`

Infrastructure 层负责外部实现细节：

- database connection 选择和 schema 初始化
- SQLite repository SQL
- PostgreSQL schema setup
- 本地文件存储与数据库内 bytes 存储
- 安全的存储路径解析

Infrastructure 代码不应该编码产品策略，除非该规则是技术不变量，例如阻止 storage path escape。

必要时，Infrastructure 可以 import Python 标准库和少量共享领域类型。

### `ui/`

UI 层负责 NiceGUI 页面和浏览器交互。

UI 代码必须通过 `/api/...` 与后端行为交互。它不能直接连接 SQLite、decode JWT，也不能直接调用 application service。

这条规则能确保权限、审计、校验和未来的副作用都统一经过 API。

## 依赖方向

推荐依赖方向：

```text
ui -> api -> application -> infrastructure
              |
              v
            domain
```

允许的例外：

- `app.py` 负责组合所有层。
- 兼容模块 `proteinhub.db`、`proteinhub.storage` 和 `proteinhub.services` 可以 re-export 新模块，服务旧 import。
- 测试在专门测试遗留兼容行为时，可以 import 兼容模块。

禁止的依赖：

- `domain` import 任意更高层。
- `infrastructure` import `api` 或 `ui`。
- `application` import FastAPI、NiceGUI 或 UI helper。
- `proteinhub/ui/` import `proteinhub.db`、`proteinhub.services` 或 `proteinhub.security`。

## 数据归属

数据库存储以下结构化数据：

- users
- projects
- project members
- proteins
- batches
- batch wells
- artifact metadata
- experiment raw-file metadata and bytes

本地开发默认使用 SQLite 和文件系统。服务器部署可以通过
`PROTEINHUB_DATABASE_URL` 切换到 PostgreSQL；该模式默认把 artifact bytes
和 protein structure bytes 存入数据库 BLOB/BYTEA 字段，同时保留相对路径
metadata 用于命名、审计和兼容已有 API。Experiment raw files 始终直接存入
数据库 BLOB/BYTEA 字段。AKTA zip 已经作为 protein artifact 存储，不在
experiment raw-file 表重复存储。

所有 artifact 路径都必须由 infrastructure storage helper 生成。用户提供的
filename 在参与路径构造前必须被 sanitize。Repository 查询不应把 bytes 字段
带入普通 API 响应；下载 bytes 必须单独经过 API 授权检查。

## 权限

权限以 project 为边界。

- 任意 project member 可以查看项目数据。
- 任意 project member 可以创建 protein 和 artifact。
- 任意 project member 可以创建 batch 和回填 batch well 结果。
- 只有 project owner 可以添加成员。
- 只有 project owner 可以删除 artifact。
- 只有全局 admin 可以调整 project 状态，例如 active、archived 和 trash。

权限检查应放在 `application/permissions.py` 或 application service 中，不应在 API 路由或 UI 页面里重复实现。

## 错误处理

Application 代码通过 `domain/errors.py` 抛出 domain errors。

API 代码把 domain errors 映射为 HTTP responses。UI 代码展示后端 API 返回的错误。

Infrastructure 代码可以为意外失败抛出技术异常。如果某个技术失败属于正常产品行为，应在 application 代码中转换为 domain error。

## 兼容模块

下面这些根模块是兼容导出：

- `proteinhub.db`
- `proteinhub.storage`
- `proteinhub.services`

新代码应改为从 canonical layered modules import。等所有内部和外部调用迁移完成后，可以移除这些兼容模块。

## 近期架构路线

1. 在 schema 变更变频繁之前加入数据库 migration。
2. 引入 typed domain models 或 DTOs，减少跨层 `dict` 使用。
3. 当 repository 继续变大时，按 aggregate 拆分 SQLite repositories。
4. 如果 NiceGUI 页面继续增长，继续在 `proteinhub/ui/` 内按页面或 workflow 拆分。
