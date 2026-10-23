# LangGraph 保险理赔 Agent（可运行示例）

这是一个用于学习 LangGraph 的完整小型项目，覆盖：

- `StateGraph`、TypedDict State、节点与普通边
- 条件路由、并行分支与 reducer
- Pydantic 结构化输出（可选真实 LLM）
- 条款检索（本地模拟 RAG）与证据 ID 校验
- `InMemorySaver` Checkpoint、`thread_id`
- `interrupt()` / `Command(resume=...)` 人工审批
- 简化权限检查、可信审批记录、幂等执行模拟
- RetryPolicy、测试和 CLI 演示

> **安全声明：**这是本地学习样例，不是可直接用于真实保险理赔或资金操作的生产系统。身份认证、数据库、向量检索、审批记录、事务与幂等服务均为演示实现。`InMemorySaver` 只在当前进程内存中保存状态，重启后不会持久化。

## 1. 环境要求

- Python 3.10+
- 建议使用独立虚拟环境

### Linux / WSL

```bash
cd langgraph_insurance_agent
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

### Windows PowerShell

```powershell
cd langgraph_insurance_agent
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

如果不想安装为项目，也可以运行 `pip install -r requirements.txt`。

## 2. 运行基础案例

```bash
python -m insurance_agent
```

命令行会创建一个高风险理赔案例，流程暂停在人工审批节点，然后演示恢复。也可分别运行：

```bash
python -m insurance_agent --scenario low
python -m insurance_agent --scenario missing
python -m insurance_agent --scenario inactive
python -m insurance_agent --scenario high
```

场景说明：
- `low`：低风险，走自动审核路径（仅模拟）。
- `missing`：材料缺失，进入补充材料分支。
- `inactive`：保单无效，终止处理。
- `high`：高风险，暂停等待人工审批；CLI 会在演示中模拟授权审核并恢复。

## 3. 运行测试

```bash
pytest -q
```

## 4. 可选：启用真实 LLM

基础版默认不需要 API Key，不调用网络，便于先理解图执行机制。

安装可选依赖：

```bash
pip install -e ".[llm]"
```

复制 `.env.example` 为 `.env` 并配置环境变量（本示例不会自动读取 `.env`，请自行在 shell 设置环境变量）：

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选；本地 OpenAI 兼容端点也可使用
export OPENAI_MODEL="gpt-4o-mini"
```

之后运行：

```bash
python -m insurance_agent --llm
```

注意：模型分析只用于生成建议，不能成为正式审批依据。示例的条款库仍是模拟数据；要接入生产 RAG，必须实现真实检索、租户权限过滤和证据来源校验。

## 5. 主要文件

```text
insurance_agent/
  __init__.py
  __main__.py       # CLI 入口与演示流程
  state.py          # State 类型
  data.py           # 模拟保单、材料与条款数据
  nodes.py          # 各业务节点、可选 LLM
  security.py       # 演示权限检查与审批记录
  graph.py          # 图构建、条件路由与并行分支
tests/
  test_workflow.py  # 关键分支测试
```

## 6. 重要实现说明

### State / Reducer
并行检查分别写入 `policy_check`、`document_check`、`clause_check`，避免多个节点同时覆盖同一字段。`risk_signals` 使用 reducer 合并各分支的风险信号。

### Checkpoint / thread_id
每次执行传入 `configurable.thread_id`。生产环境要在服务端把 thread 与经过认证的用户/租户绑定；`thread_id` 本身不是访问凭据。

### Human-in-the-loop
`human_review` 使用 `interrupt()`。CLI 只为了展示而模拟审批。真实系统应先在独立审批服务里验证审核人身份与权限，持久化正式审批记录，再恢复工作流；不能把浏览器传来的 `{"approved": true}` 直接当作可信凭据。

### 业务操作和幂等
`execute_claim` 会调用演示版授权检查和幂等模拟器。真实资金操作必须由业务服务从可信数据库重新验证案件状态、正式审批记录、用户权限，并通过事务/幂等键防止重复执行。

### RetryPolicy
条款检索节点配置有限重试。权限拒绝不应通过重试“解决”；外部副作用节点应先实现幂等，再考虑重试。
