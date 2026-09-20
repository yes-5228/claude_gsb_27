# 公厕保洁巡查记录系统

面向城市公厕管养单位的巡查记录与整改闭环管理系统，覆盖 **公厕台账 → 保洁巡查 → 问题上报 → 整改跟踪** 四条业务主线。后端为 FastAPI + SQLAlchemy，前端为 React + Vite，前后端均按模块拆分，可单独开发、单独部署。

## 功能模块

| 模块 | 页面/入口 | 主要能力 |
| --- | --- | --- |
| 总览看板 | `/` | 核心指标卡（含近 7 日漏检）、巡查/漏检/问题趋势、整改状态/分类/严重程度分布、区域运行情况、重点关注公厕、最新问题与巡查 |
| 公厕台账 | `/restrooms`、`/restrooms/:id` | 台账增删改查、区域与状态筛选、公厕详情（档案 + 历史巡查 + 历史问题 + 状态变更记录）、开放状态变更联动、关联数据删除保护 |
| 保洁巡查 | `/inspections` | 8 项检查项打分、自动折算百分制得分与等级、班次/日期/结论筛选、巡查详情、一键转问题上报；停用公厕不可录入 |
| 巡查任务 | `/tasks` | 每座开放公厕每日一条任务、按日生成（幂等不重复）、随停用自动取消、随恢复自动补回、过期未执行标记漏检 |
| 问题上报 | `/issues`、`/issues/:id` | 问题上报（可关联巡查记录）、分类/程度/期限、整改流程流转、整改轨迹时间线、超期预警、追加跟进记录、停用期限顺延留痕 |
| 月度考核 | `/assessments` | 按自然月生成考核快照（应巡/实巡/漏检/均分/问题）、发布后固化不变；整改期限顺延规则维护（带生效时间） |

其他页面不会互相混杂：台账、巡查、问题各自独立成页，详情页再做跨模块的关联展示。

## 技术栈

- 后端：FastAPI 0.115、SQLAlchemy 2.0、Pydantic v2、Uvicorn；数据库默认 SQLite，容器中可切换 PostgreSQL 16
- 前端：React 18、React Router 6、Vite 6；不使用 UI 组件库，样式集中在 `src/styles/global.css`
- 部署：Docker Compose 编排 PostgreSQL + 后端 + Nginx 前端（Nginx 同时反代 `/api`）

## 目录结构

```
.
├── backend
│   ├── app
│   │   ├── api/v1/endpoints      # 路由层：restrooms / inspections / tasks / issues / rules / assessments / stats / meta
│   │   ├── core                 # 配置、数据库、业务常量、领域异常
│   │   ├── models               # ORM 模型：公厕、巡查、任务、问题、整改流水、状态流水、顺延规则、月度考核
│   │   ├── schemas              # Pydantic 出入参模型
│   │   ├── services             # 业务规则层：台账、巡查、任务、问题整改、状态联动、顺延规则、月度考核、评分、统计
│   │   ├── seed.py              # 演示数据生成
│   │   └── main.py              # 应用入口（含异常处理、CORS、健康检查）
│   ├── tests                    # pytest 接口测试
│   ├── Dockerfile
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── api                  # 按资源拆分的接口封装 + 统一 fetch 客户端
│   │   ├── components           # 通用组件：表格、分页、弹窗、标签、图表、时间线等
│   │   ├── hooks                # useAsync / useListQuery / useDictionaries
│   │   ├── pages                # dashboard / restrooms / inspections / tasks / issues / assessments 六个模块
│   │   ├── utils                # 时间格式化、评分换算
│   │   └── styles/global.css
│   ├── nginx.conf
│   └── Dockerfile
└── docker-compose.yml
```

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
docker compose up -d --build
```

启动后：

- 前端界面：http://localhost:8080
- 后端接口文档：http://localhost:8000/docs （也可通过 http://localhost:8080/docs 访问）
- 健康检查：http://localhost:8000/health

三个服务均带健康检查，`backend` 等待 `db` 健康后启动，`frontend` 等待 `backend` 健康后启动。首次启动会自动建表并写入演示数据。

停止与清理：

```bash
docker compose down        # 停止容器
docker compose down -v     # 同时删除数据库卷（下次启动重新生成演示数据）
```

### 方式二：本地开发

后端（默认使用 SQLite，数据库文件为 `backend/data/app.db`）：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173，/api 自动代理到 127.0.0.1:8000
```

若后端不在默认端口，可指定代理目标：

```bash
set VITE_PROXY_TARGET=http://127.0.0.1:8020   # macOS/Linux: export VITE_PROXY_TARGET=...
npm run dev
```

## 环境变量

后端（均可用环境变量覆盖，见 `backend/app/core/config.py`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/app.db` | 数据库连接串；容器中为 `postgresql+psycopg://restroom:restroom_pass@db:5432/restroom` |
| `SEED_ON_STARTUP` | `true` | 启动时若库为空则写入演示数据 |
| `CORS_ORIGINS` | `*` | 允许跨域来源，逗号分隔 |
| `SQL_ECHO` | `false` | 是否打印 SQL |

前端：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_API_BASE` | `/api/v1` | 接口前缀，构建时注入 |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` | 仅开发模式下 Vite 代理目标 |

## 接口一览

所有接口前缀为 `/api/v1`，完整文档见 `/docs`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/restrooms` | 台账分页查询（keyword/district/status/grade/排序/分页） |
| POST | `/restrooms` | 新增公厕，编号留空自动生成 `WC-0001` |
| GET | `/restrooms/{id}` | 详情，含巡查次数、均分、未闭环问题数、最近状态变更时间 |
| PATCH | `/restrooms/{id}` | 局部更新（开放状态不可在此修改） |
| POST | `/restrooms/{id}/status` | 变更开放状态，联动巡查任务与整改期限并留痕 |
| GET | `/restrooms/{id}/status-events` | 状态变更流水（停用/恢复全程留痕） |
| DELETE | `/restrooms/{id}?force=` | 删除；有巡查或问题记录时返回 409，`force=true` 才级联删除 |
| GET | `/restrooms/meta/districts` | 区域列表（筛选下拉用） |
| GET | `/inspections` | 巡查记录查询（restroom_id/district/inspector/shift/result/日期区间/关键字） |
| POST | `/inspections` | 新增巡查，服务端按检查项自动算分、定级、判定结论；巡查时刻处于停用状态的公厕返回 400 |
| GET/PATCH/DELETE | `/inspections/{id}` | 详情 / 更新 / 删除 |
| GET | `/inspection-tasks` | 巡查任务查询（task_date/restroom_id/status），查询当日及未来日期时自动补齐生成 |
| POST | `/inspection-tasks/generate` | 生成指定日期的巡查任务（幂等，已存在不重复） |
| GET | `/issues` | 问题查询（status/category/severity/district/overdue/open_only/日期区间/关键字） |
| POST | `/issues` | 上报问题，自动生成编号 `WT-YYYYMMDD-001` 并写入首条整改流水 |
| GET/PATCH/DELETE | `/issues/{id}` | 详情（含完整整改轨迹）/ 更新 / 删除 |
| GET | `/issues/{id}/transitions` | 当前状态可执行的流转动作 |
| POST | `/issues/{id}/transitions` | 推进整改状态（越级流转返回 400） |
| POST | `/issues/{id}/records` | 追加跟进记录（不改变状态） |
| GET/POST | `/deadline-rules` | 顺延规则列表 / 新增（带生效时间） |
| PATCH | `/deadline-rules/{id}` | 更新/启停顺延规则 |
| GET | `/assessments` | 月度考核列表（month/district 过滤） |
| POST | `/assessments/generate` | 生成指定月份考核快照（已生成的跳过，不覆盖） |
| GET | `/stats/overview` | 核心指标（含暂停使用数量、近 7 日漏检） |
| GET | `/stats/dashboard` | 看板聚合数据（趋势含每日漏检、分布、区域、排行、最新记录） |
| GET | `/meta/dictionaries` | 枚举字典（状态、分类、程度、检查项、流转规则、任务状态） |
| GET | `/meta/restroom-options` | 公厕下拉选项（含开放状态） |
| GET | `/health` | 健康检查 |

## 业务规则

- **巡查评分**：8 个检查项各 0-10 分，得分 = 总得分 / 满分 × 100；≥90 优秀、≥80 良好、≥70 合格，其余不合格。任一检查项低于 6 分或等级为不合格时，巡查结论自动置为「发现问题」。
- **问题编号**：`WT-` + 上报日期 + 当日三位流水号。
- **整改闭环**：`待整改 → 整改中 → 待验收 → 已完成 → 已关闭`；`待验证` 阶段可被驳回退回 `整改中`，`待整改/整改中` 可直接作废关闭。每次流转都会写入一条整改流水（动作、原状态、新状态、操作人、说明），详情页以时间线呈现。
- **超期预警**：整改期限早于当前时间且状态仍处于未闭环（待整改/整改中/待验收）时，列表与详情页显示「已超期」，看板统计超期数量。
- **开放状态联动**：开放状态只能通过「状态变更」接口调整（`POST /restrooms/{id}/status`），每次变更写入状态流水（原状态、新状态、原因、操作人、时间）。开放 → 维修中/暂停使用时：当日及以后的待执行巡查任务自动取消，未闭环问题按生效中的顺延规则顺延期限并在整改流水中说明原因；恢复开放时：被取消的任务原行补回。维修中 ↔ 暂停使用 之间切换只留痕，不重复取消、不重复顺延。
- **巡查任务**：每座开放公厕每日一条，按 `(公厕, 日期)` 唯一约束保证幂等——重复生成不重复、反复启停不漏项；提交巡查记录后对应任务自动完成；过去日期仍未执行的任务展示为「漏检」。新增巡查记录时按巡查时刻的开放状态判定，停用期间返回 400。
- **期限顺延规则**：规则包含顺延天数、触发状态（维修中/暂停使用）与生效时间，只影响生效之后的判定；判定时取当时生效的最新一条规则。修改规则不会改写历史顺延记录。
- **应巡与漏检**：以状态流水推算每座公厕每天的开放时段——一天内开放过即应巡 1 次（反复切换不重复计），全天停用不应巡（停用空白不算漏检），建档日之前不应巡；应巡日无巡查记录计 1 次漏检。看板展示近 7 日漏检与每日漏检趋势，恢复开放后各项数字自动还原。
- **月度考核**：按自然月为每座公厕生成考核快照（应巡天数、实巡次数、漏检天数、巡查均分、当月新增/闭环问题、考核得分与结果），得分 = 巡查均分 − 漏检天数 × 2（下限 0）；当月只统计到昨天。已生成的考核不重复生成、不随后续状态变化改变。
- **删除保护**：删除公厕时若已存在巡查或问题记录，接口返回 409 并提示数量，需要显式 `force=true` 才会级联删除；前端会二次确认。

## 演示数据

`SEED_ON_STARTUP=true`（默认）且数据库为空时，会自动写入：10 座公厕（4 个区域、三类等级、含维修/停用状态）、近 14 天约 90 条巡查记录、13 条不同整改阶段的问题及其完整整改轨迹、1 条默认顺延规则（停用每次顺延 3 天）、上月月度考核快照。数据由固定随机种子生成，结果可复现；如需重置，删除 `backend/data/app.db`（或 `docker compose down -v`）后重启即可。

## 测试与验证

```bash
cd backend && pytest -q          # 接口测试（覆盖台账 CRUD、删除保护、评分、流程流转、状态联动、顺延规则、漏检统计、月度考核、统计）
cd frontend && npm run build     # 生产构建
```

本项目完成时已实际运行验证：

- 后端 `pytest`：13 个用例全部通过；`/health`、台账/巡查/任务/问题/规则/考核/统计/字典接口均返回预期数据。
- 前端 `npm run build`：构建成功（74 个模块）。
- 浏览器端到端验证（Chromium 无头模式）：看板漏检卡片与趋势系列、任务生成与列表、公厕状态变更（联动提示、留痕时间线）、编辑表单状态字段禁用、月度考核生成与顺延规则页签、巡查表单非开放公厕禁用。全程无控制台报错。
- Docker Compose：`docker compose up -d --build` 后 `db`、`backend`、`frontend` 三个容器均达到 healthy，通过 Nginx 访问前端并调用 `/api/v1/*` 数据正常，即容器化链路（Nginx → FastAPI → PostgreSQL）完整可用。

## 常见问题

- **端口被占用**：若 8000/8080 已被占用，可用覆盖文件改端口，例如 `docker compose -f docker-compose.yml -f override.yml up -d`，其中 `override.yml` 写 `services: { backend: { ports: ["8010:8000"] } }`。
- **想看 SQLite 而不是 PostgreSQL**：把 `backend` 服务的 `DATABASE_URL` 改为 `sqlite:///./data/app.db` 即可，无需 `db` 服务。
- **接口 422**：后端把参数校验错误统一转成中文可读文案，前端会直接弹出提示，例如「参数校验失败 - name: String should have at least 1 character」。
- **越级流转报错**：属于预期行为，接口会返回当前状态允许流转的目标状态列表，前端也只会展示合法动作。
