import os
import sys
import time

sys.path.insert(0, "src")

# Configure for real search + DeepSeek
os.environ["INSIGHT_GRAPH_LLM_BASE_URL"] = "https://api.deepseek.com/v1"
os.environ["INSIGHT_GRAPH_LLM_API_KEY"] = "sk-9ee03adb2ddc43ff8a5ce4a09887d224"
os.environ["INSIGHT_GRAPH_LLM_MODEL"] = "deepseek-chat"
os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] = "llm"
os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] = "llm"
os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] = "serpapi"
os.environ["INSIGHT_GRAPH_SERPAPI_KEY"] = "bb6ac21c7517fd94953fa00d34eade2dedb91822a26f9a907cdec551021808cb"
os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] = "1"
os.environ["INSIGHT_GRAPH_SEARCH_LIMIT"] = "10"

from insight_graph.graph import run_research_with_events

QUERY = "小米公司 Xiaomi Corporation 2025年度深度分析：财务表现、产品生态、竞争格局、市场机会与风险"

print("=" * 70)
print("小米公司深度分析报告生成（真实搜索数据）")
print("=" * 70)
print(f"查询: {QUERY}")
print(f"搜索: SerpAPI (Google)")
print(f"分析: DeepSeek")
print("=" * 70)
print()

started = time.time()
llm_calls = []
tool_calls = []


def emit(event):
    etype = event.get("type", "")
    stage = event.get("stage", "")
    record = event.get("record", {})

    if etype == "stage_started":
        print(f"[开始] {stage}")
    elif etype == "stage_ended":
        print(f"[完成] {stage}")
    elif etype == "llm_call":
        call = {
            "stage": stage,
            "model": record.get("model", "?"),
            "input": record.get("input_tokens", 0),
            "output": record.get("output_tokens", 0),
            "total": record.get("total_tokens", 0),
            "ok": record.get("success", False),
        }
        llm_calls.append(call)
        status = "OK" if call["ok"] else "FAIL"
        print(
            f"  [LLM] {stage} - in:{call['input']} out:{call['output']} "
            f"total:{call['total']} {status}"
        )
    elif etype == "tool_call":
        tool_calls.append(record)
        tool_name = record.get("tool_name", "?") if isinstance(record, dict) else "?"
        print(f"  [工具] {tool_name}")
    elif etype == "report_ready":
        print("[报告生成完成]")


result = run_research_with_events(QUERY, emit)

elapsed = time.time() - started

print()
print("=" * 70)
print("执行统计")
print("=" * 70)
print(f"总耗时: {elapsed:.1f} 秒")
print(f"LLM 调用: {len(llm_calls)} 次")
print(f"工具调用: {len(tool_calls)} 次")
if llm_calls:
    total_in = sum(c["input"] for c in llm_calls)
    total_out = sum(c["output"] for c in llm_calls)
    total_tokens = sum(c["total"] for c in llm_calls)
    print(f"总 Token: 输入 {total_in} + 输出 {total_out} = {total_tokens}")
print(f"证据条数: {len(result.evidence_pool)}")
print(f"发现条数: {len(result.findings)}")
print(f"报告长度: {len(result.report_markdown or '')} 字符")

# Save report
os.makedirs("reports", exist_ok=True)
path = os.path.join("reports", "xiaomi-serpapi-analysis.md")
with open(path, "w", encoding="utf-8") as f:
    f.write(result.report_markdown or "(empty)")
print(f"保存路径: {path}")

print()
print("=" * 70)
print("报告内容（前 4000 字符）")
print("=" * 70)
print((result.report_markdown or "")[:4000])
if len(result.report_markdown or "") > 4000:
    print()
    print(f"... (还有 {len(result.report_markdown) - 4000} 字符)")
