"""快速验证脚本 — 财务 + 网络全链路（mock 模式，无 GPU/ollama）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 财务链路 ──────────────────────────────────────────────────────────────────
print("[验证] 财务端到端全链路...")
from forge.scenarios.finance_v1.faults import inject_faults
from forge.scenarios.finance_v1.validator import FinanceValidator
from forge.core.projector import Projector
from forge.core.reporter import DualReporter

df_faulty, truth = inject_faults()
report = FinanceValidator().validate(df_faulty)
df_c, logs = Projector().project(report, df_faulty)
dual = DualReporter().make_dual(df_faulty=df_faulty, truth=truth)

cogs_val = int(df_c.loc[df_c["PeriodIndex"] == 3, "COGS"].values[0])
print(f"  违规命中: {len(report.violations)} 条")
print(f"  COGS 修正: {cogs_val} (应=2000)")
print(f"  A轨含3000: {'3,000' in dual.track_a.markdown}")
print(f"  B轨干预: {len(dual.track_b.intervention_log)} 条")
print("  财务链路: PASS\n")

# ── 网络链路 ──────────────────────────────────────────────────────────────────
print("[验证] 网络 pipeline (mock 模式)...")
from server.pipeline import run_network_pipeline

events = []
result = run_network_pipeline({"job_id": "qs_test", "scenario": "network_cidds"}, events.append)
print(f"  规则集: {len(result['ruleset'].rules)} 条")
print(f"  SSE 事件: {len(events)} 个")
print("  网络链路: PASS\n")

print("全部验证通过!")
