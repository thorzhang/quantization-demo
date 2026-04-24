# 📌 量化系统项目说明（MVP阶段）

## 一、项目目标

构建一个基于 Python 的量化分析系统（非实时交易），具备以下能力：

* 获取股票市场数据（免费数据源）
* 数据入库与管理
* 基于策略进行股票推荐（如技术指标）
* 后续支持大模型（LLM）进行策略解释与辅助决策

当前阶段为 **MVP（最小可用系统）**，强调：

* 简单
* 可运行
* 可扩展

---

## 二、技术框架

### 后端框架

* FastApi（API服务）

### ORM

* SQLAlchemy 2.0（必须使用2.0写法）

### 数据库

* PostgreSQL

### 主键规范

* 每张表：

    * 主键字段：`id`
    * 类型：`UUID`
    * 生成方式：**应用层 uuidv7**

### 数据源

* akshare（免费，无需token）

### 依赖管理

* uv

---

## 三、核心技术约束

### 1. SQLAlchemy规范

* 使用 SQLAlchemy 2.0 风格（Mapped / mapped_column）
* 禁止使用 1.x 写法

---

### 2. 数据库设计规范

#### 表命名

* 所有表必须以 `t_` 开头

#### 主键规范

```python
id: Mapped[UUID] = mapped_column(
    PG_UUID(as_uuid=True),
    primary_key=True,
    default=uuid7
)
```

#### UUID策略

* 使用 uuidv7（时间有序）
* 由应用层生成（不依赖数据库）

---

### 3. 分层架构（必须遵守）

```text
API → Service → Repository → DB
```

#### 各层职责

| 层级         | 职责                |
|------------|-------------------|
| API        | 参数接收、返回响应         |
| Service    | 业务逻辑              |
| Repository | 数据库操作             |
| Model      | ORM模型             |
| Schema     | 数据校验（Pydantic v2） |

---

### 4. 数据处理原则

* 外部数据 → API → Service → Repository → db，不要跨层
* Repository 不做业务逻辑
* Model 不参与业务逻辑

### 5. 方法命名原则

* 方法的参数和返回值尽量有类型声明
* 方法以英语动词开头
* 方法定义符合python规范

---

## 四、项目目录结构

```text
app/
├── api/
│   ├── v1/
│   │   ├── endpoint/
│   │   ├── router.py
├── cache/
├── core/
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

## 五、当前已实现模块（MVP阶段）

### 1. 数据采集模块

* 数据源：akshare
* 功能：

    * 获取股票日线数据
    * 转换为 ORM 对象
    * 入库 PostgreSQL

---

### 2. 数据存储

表：`t_stock_daily`

字段：

| 字段     | 说明        |
|--------|-----------|
| id     | UUIDv7 主键 |
| symbol | 股票代码      |
| date   | 日期        |
| open   | 开盘价       |
| close  | 收盘价       |
| high   | 最高价       |
| low    | 最低价       |
| volume | 成交量       |

---

### 3. API接口

```http
POST /fetch
```

功能：

* 拉取指定股票数据并入库

---

## 六、已确定设计原则

### ✔ 简化优先

* 不做过度设计
* 每一步可运行

### ✔ 可扩展

* 后续支持：

    * 策略引擎
    * 回测
    * 大模型接入

### ✔ 解耦

* 严格分层
* 不跨层调用

---

## 七、明确暂不实现（避免复杂度失控）

当前阶段禁止引入：

* ❌ 实时交易
* ❌ 回测系统
* ❌ 多策略框架
* ❌ 微服务拆分
* ❌ 大模型直接选股

---

## 八、下一步规划

### Step 1（已完成）

* 数据采集 + 入库 ✅

### Step 2（下一步）

* 策略模块（Strategy Service）

    * MA5 / MA20
    * 输出：BUY / SELL / HOLD

### Step 3

* 推荐接口

### Step 4

* 大模型接入（解释策略，不直接决策）

---

## 九、全局开发约定

### 命名规范

* 表名：t_xxx
* 类名：PascalCase
* 字段：snake_case

---

### 代码原则

* 不在 Controller 写业务逻辑
* 不在 Repository 写计算逻辑
* Service 是唯一业务入口

---

### 数据一致性

* 后续必须支持：

    * 唯一索引（symbol + date）
    * 去重 / upsert

---

## 十、总结

当前系统定位：

> 一个“可扩展的量化分析后端基础框架”，而不是完整量化平台。

核心目标：

* 快速构建
* 稳定演进
* 逐步增加能力

---

（此文档作为后续开发的统一上下文，不再重复说明，你的回复尽量简单明了，最后不要生成建议问题，尽量节省token消耗，以便可以多问答几轮）
