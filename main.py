
from engine import BusinessModelEngineV2_1
import pandas as pd

def print_report(code, name=""):
    engine = BusinessModelEngineV2_1()
    print(f"\n🔍 正在诊断: {name} ({code}) ...")
    result = engine.diagnose(code)
    if "error" in result: print(f"❌ 诊断失败: {result['error']}"); return
    print("="*60)
    print(f"🏢 公司名称: {name} ({code})")
    print(f"🏷️  识别形态: 【{result['business_model']}】")
    print("-" * 60)
    print(pd.DataFrame([result['metrics']]).T.to_string(header=False))
    print("="*60)
    advice = {"收租型": "💰 策略: 收息防守。", "消费心智型": "🛡️ 策略: 长线复利。",
              "周期制造型": "🎢 策略: 周期博弈。", "技术迭代型": "🚀 策略: 成长进攻。",
              "项目工程型": "⚠️ 策略: 谨慎参与。", "消费心智型(类收租)": "👑 策略: 顶级资产。"}
    print(advice.get(result['business_model'], "💡 策略: 需人工复核。"))

if __name__ == "__main__":
    for code, name in [("002714", "牧原股份"), ("600519", "贵州茅台"), ("601668", "中国建筑")]:
        print_report(code, name)
