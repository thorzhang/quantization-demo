# 📌 量化系统项目说明（MVP）

## 一、项目目标

构建一个基于 Python 的量化分析系统（非实时交易），具备：

* 股票数据获取（akshare）
* 数据入库与管理（PostgreSQL）
* 基于策略的股票推荐（如 MA）
* 后续支持 LLM 做策略解释（不参与决策，需要给出决策建议）

当前阶段：**MVP（最小可用系统）**

核心原则：

* 简单可运行
* 可扩展
* 不过度设计

---

## 二、技术选型

| 模块    | 技术                 |
|-------|--------------------|
| Web框架 | FastAPI            |
| ORM   | SQLAlchemy 2.0（强制） |
| 数据库   | PostgreSQL         |
| 数据源   | akshare            |
| 依赖管理  | uv                 |

---

## 三、系统架构（强约束）

分层结构：

API → Service → Repository → UOW → DB

职责划分：

| 层级         | 职责                |
|------------|-------------------|
| API        | 参数接收、返回响应         |
| Service    | 业务逻辑              |
| Repository | 数据库操作             |
| Model      | ORM模型             |
| Schema     | 数据校验（Pydantic v2） |

强制约束：

* 禁止跨层调用
* Service 是唯一业务入口
* Repository 不写业务逻辑
* Model 不参与业务逻辑

---

## 四、开发规范（统一约束）

### 1. ORM 规范

* 必须使用 SQLAlchemy 2.0 风格（Mapped / mapped_column）
* 禁止使用 1.x 写法

---

### 2. 数据库规范

#### 表命名

* 所有表必须使用 `t_` 前缀

#### 主键规范

id: Mapped[UUID] = mapped_column(
PG_UUID(as_uuid=True),
primary_key=True,
default=uuid7
)

* 使用 UUIDv7（时间有序）
* 必须由应用层生成

#### 数据一致性

* 唯一索引：`symbol + date`
* 必须支持：
    * 去重
    * upsert

---

### 3. 命名规范

| 类型 | 规则         |
|----|------------|
| 表名 | t_xxx      |
| 类名 | PascalCase |
| 字段 | snake_case |
| 方法 | 动词开头       |

---

### 4. API 规范

* GET：查询
* POST：新增
* PUT：更新
* DELETE：删除
* URL 使用名词形式

---

### 5. 代码规范

* 方法必须尽量具备类型声明
* 不在 Controller 写业务逻辑
* 不在 Repository 写计算逻辑

---

### 6. 数据流规范

外部数据 → API → Service → Repository → DB

禁止跨层流转。

---

### 7. 异步任务规范（Celery）

* Task 只负责调度
* 不写业务逻辑
* 必须调用 Service
* 每个任务独立事务

---

## 五、项目目录结构（完整保留）

```text
app/
├── api/
│   ├── v1/
│   │   ├── endpoint/
│   │   ├── router.py
├── cache/
├── core/
│   ├── constant/
│   ├── dep/
│   ├── enums/
│   ├── exception/
│   ├── log/
│   ├── response/
│   ├── security/
│   ├── setting/
├── db/             # 数据库连接、Base
├── dep/            # 各项依赖
├── integration/    # 各项集成
│   ├── datasource/ # 集成三个A股拉取源
├── middleware/     # 中间件
├── model/          # ORM模型（SQLAlchemy 2）
├── redis/          
├── repository/     # 数据访问层
├── schema/         # 数据校验（Pydantic v2）
├── service/        # 业务逻辑
├── task/           # celery task
├── util/           # 工具类

```

---

## 六、已实现模块（MVP）

### 1. 数据采集

* 数据源：akshare
* 能力：
    * 获取股票日线数据
    * 转换为 ORM 对象
    * 入库 PostgreSQL

---

### 2. 核心数据表：t_stock_daily

| 字段        | 说明        |
|-----------|-----------|
| id        | UUIDv7 主键 |
| symbol    | 股票代码      |
| date      | 日期        |
| open      | 开盘价       |
| close     | 收盘价       |
| high      | 最高价       |
| low       | 最低价       |
| pre_close | 昨收价       |
| volume    | 成交量       |
| amount    | 成交额       |
| turnover  | 换手率       |
| pct_chg   | 涨跌幅       |
| pe_ttm    | 市盈率       |
| pb_mrq    | 市净率       |
| is_st     | 是否ST      |

---

## 七、范围限制（必须遵守）

当前阶段禁止引入：

* ❌ 实时交易
* ❌ 回测系统
* ❌ 多策略框架
* ❌ 微服务拆分
* ❌ LLM直接选股

---

## 八、演进路线

### Step 1（已完成）

* 数据采集 + 入库

### Step 2（当前阶段）

* 策略模块（Strategy Service）
    * MA5 / MA20
    * 输出：BUY / SELL / HOLD

### Step 3

* 推荐接口

### Step 4

* LLM 接入（仅用于策略解释）

---

## 九、系统定位

一个“可扩展的量化分析后端基础框架”

目标：

* 快速构建
* 稳定演进
* 渐进增强能力  
