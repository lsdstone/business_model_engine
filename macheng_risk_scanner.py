import requests
import pandas as pd
import numpy as np
import time

# 设置请求头，模拟浏览器访问
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://emweb.securities.eastmoney.com/"
}

# ================= 1. 定义核心样本池及对应的生意模式 =================
# 格式: "股票代码": ("公司名称", "生意模式")
test_pool = {
    "600519": ("贵州茅台", "消费心智型"),
    "603195": ("公牛集团", "消费心智型"),
    "000333": ("美的集团", "复合/运营型"),
    "000651": ("格力电器", "复合/运营型"),
    "002415": ("海康威视", "技术迭代型"),
    "002714": ("牧原股份", "周期制造型"),
    "601668": ("中国建筑", "项目工程型")
}

# ================= 2. 定义 V4.1 数据抓取与计算函数 =================
def get_v41_metrics(code, name, biz_type):
    """
    抓取指定股票的最新财报数据，并计算 V4.1 专属麦城指标
    """
    try:
        # --- 请求 1: 获取主要财务指标 (利润表相关，取近2年年报对比) ---
        url1 = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        p1 = {
            "reportName": "RPT_F10_FINANCE_MAINFINADATA", "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")', "pageNumber": 1, "pageSize": 10,
            "sortTypes": "-1", "sortColumns": "REPORT_DATE", "source": "HSF10", "client": "PC"
        }
        r1 = requests.get(url1, params=p1, headers=headers, timeout=10).json()
        d1 = r1.get('result', {}).get('data', [])
        
        # 筛选出年报 (12-31) 数据，取最新的两年
        annual = [d for d in d1 if '12-31' in str(d.get('REPORT_DATE', ''))][:2]
        if len(annual) < 2: 
            return {"公司": name, "模式": biz_type, "Error": "年报数据不足"}
        
        latest_inc = annual[0]
        prev_inc = annual[1]
        
        # 提取利润表核心数据
        rev = latest_inc.get('TOTALOPERATEREVE', 0) or 0
        prev_rev = prev_inc.get('TOTALOPERATEREVE', 0) or 0
        np = latest_inc.get('PARENTNETPROFIT', 0) or 0
        sale_exp = latest_inc.get('SALE_EXPENSE', 0) or 0
        prev_sale_exp = prev_inc.get('SALE_EXPENSE', 0) or 0

        # --- 请求 2: 获取资产负债表明细 (取最新年报) ---
        url2 = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        p2 = {
            "reportName": "RPT_DMSK_FN_BALANCE", "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")', "pageNumber": 1, "pageSize": 5,
            "sortTypes": "-1", "sortColumns": "REPORT_DATE", "source": "HSF10", "client": "PC"
        }
        r2 = requests.get(url2, params=p2, headers=headers, timeout=10).json()
        bs_data = r2.get('result', {}).get('data', [])
        latest_bs = bs_data[0] if bs_data else {}
        
        # 提取资产负债表核心数据
        ar = latest_bs.get('ACCOUNTS_RECE', 0) or 0
        inv = latest_bs.get('INVENTORY', 0) or 0
        ta = latest_bs.get('TOTAL_ASSETS', 0) or 0
        te = latest_bs.get('TOTAL_EQUITY', 0) or 0
        fa = latest_bs.get('FIXED_ASSET', 0) or 0
        
        # 寻找商誉字段 (东方财富接口字段名可能变动，进行模糊匹配)
        goodwill = 0
        for k, v in latest_bs.items():
            if 'GOODWILL' in k.upper() or 'SHANGYU' in k.upper():
                goodwill = v or 0
                break

        # --- 请求 3: 获取员工人数 ---
        url3 = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        p3 = {
            "reportName": "RPT_F10_ORG_BASICINFO", "columns": "TOTAL_NUM",
            "filter": f'(SECURITY_CODE="{code}")', "pageNumber": 1, "pageSize": 1,
            "source": "HSF10", "client": "PC"
        }
        r3 = requests.get(url3, params=p3, headers=headers, timeout=8).json()
        emp_data = r3.get('result', {}).get('data', [{}])
        emp = emp_data[0].get('TOTAL_NUM', 1) or 1

        # ================= 3. V4.1 专属麦城指标计算 =================
        
        # 1. 消费心智型：品牌力衰退指标 = (本期销售费用率 - 上期销售费用率)
        sale_margin = (sale_exp / rev * 100) if rev > 0 else 0
        prev_sale_margin = (prev_sale_exp / prev_rev * 100) if prev_rev > 0 else 0
        sale_margin_delta = sale_margin - prev_sale_margin
        
        # 2. 复合/运营型：组织熵增 = 人均创利(万) + 商誉/净资产(%)
        np_per_emp = (np / 1e8) / (emp / 10000) if emp > 0 else 0
        gw_ratio = (goodwill / te * 100) if te > 0 else 0
        
        # 3. 技术迭代型：被迫垫资指标 = 应收 / 营收 (%)
        ar_to_rev = (ar / rev * 100) if rev > 0 else 0
        
        # 4. 周期制造型：重资产包袱 = 固定资产 / 总资产 (%)
        fa_ratio = (fa / ta * 100) if ta > 0 else 0
        
        # 5. 项目工程型：资金链紧绷 = (应收 + 存货) / 总资产 (%)
        ar_inv_to_ta = ((ar + inv) / ta * 100) if ta > 0 else 0
        
        # 返回计算结果字典
        return {
            "公司": name,
            "模式": biz_type,
            "销费率变化(%)": round(sale_margin_delta, 2),
            "人均创利(万)": round(np_per_emp, 1),
            "商誉/净资产(%)": round(gw_ratio, 1),
            "应收/营收(%)": round(ar_to_rev, 1),
            "固资/总资产(%)": round(fa_ratio, 1),
            "(应收+存货)/总资产(%)": round(ar_inv_to_ta, 1)
        }
        
    except Exception as e:
        return {"公司": name, "模式": biz_type, "Error": str(e)}


# ================= 4. 主执行流程 =================
if __name__ == "__main__":
    results = []
    print("正在连接东方财富数据中心，抓取最新财报数据...\n")
    
    for code, (name, biz_type) in test_pool.items():
        metrics = get_v41_metrics(code, name, biz_type)
        if metrics:
            results.append(metrics)
        time.sleep(0.5) # 控制请求频率，防止被封IP

    df = pd.DataFrame(results)

    # ================= 5. 预警逻辑判断 (V4.1 核心) =================
    def check_alert_v41(row):
        alerts = []
        mode = row["模式"]
        
        # 消费心智型：品牌力衰退 或 人效低下
        if mode == "消费心智型":
            if row.get("销费率变化(%)", 0) > 0: alerts.append("品牌力衰退")
            if row.get("人均创利(万)", 999) < 30: alerts.append("人效低下")
            
        # 复合/运营型：组织臃肿 或 并购暴雷
        if mode == "复合/运营型":
            if row.get("人均创利(万)", 999) < 25: alerts.append("组织臃肿")
            if row.get("商誉/净资产(%)", 0) > 5: alerts.append("商誉暴雷风险")
            
        # 技术迭代型：被迫垫资
        if mode == "技术迭代型" and row.get("应收/营收(%)", 0) > 25:
            alerts.append("被迫垫资")
            
        # 周期制造型：重资产包袱
        if mode == "周期制造型" and row.get("固资/总资产(%)", 0) > 40:
            alerts.append("重资产包袱")
            
        # 项目工程型：资金链紧绷
        if mode == "项目工程型" and row.get("(应收+存货)/总资产(%)", 0) > 30:
            alerts.append("资金链紧绷")
            
        return "⚠️ " + ", ".join(alerts) if alerts else "✅ 安全"

    # 应用预警逻辑
    df["麦城预警"] = df.apply(check_alert_v41, axis=1)

    # ================= 6. 格式化输出结果 =================
    print("=" * 130)
    print("🚨 V4.1 麦城指标量化引擎 · 专属模式致命风险扫描 (最终修正版)")
    print("=" * 130)
    print("【麦城警戒线】:")
    print(" 消费型: 销费率变化 > 0 (品牌力衰退) OR 人均创利 < 30万")
    print(" 运营型: 人均创利 < 25万 (组织臃肿) OR 商誉/净资产 > 5% (并购暴雷)")
    print(" 技术型: 应收/营收 > 25% (被迫垫资，坏账风险)")
    print(" 周期型: 固资/总资产 > 40% (重资产包袱，折旧绞肉机)")
    print(" 工程型: (应收+存货)/总资产 > 30% (资金链紧绷)")
    print("=" * 130)

    for index, row in df.iterrows():
        print(f"【{row['公司']}】 ({row['模式']})")
        print(f"  销费率变化: {row.get('销费率变化(%)', 'N/A')}% | 人均创利: {row.get('人均创利(万)', 'N/A')}万 | 商誉/净资产: {row.get('商誉/净资产(%)', 'N/A')}%")
        print(f"  应收/营收: {row.get('应收/营收(%)', 'N/A')}% | 固资/总资产: {row.get('固资/总资产(%)', 'N/A')}% | (应收+存货)/总资产: {row.get('(应收+存货)/总资产(%)', 'N/A')}%")
        print(f"  >>> 麦城预警: {row['麦城预警']}")
        print("-" * 130)
