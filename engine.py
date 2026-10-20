
import requests
import numpy as np
import time

class BusinessModelEngineV2_1:
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://emweb.securities.eastmoney.com/"}

    def _get_income_summary(self, code):
        url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        params = {"reportName": "RPT_F10_FINANCE_MAINFINADATA", "columns": "ALL",
                  "filter": f'(SECURITY_CODE="{code}")', "pageNumber": 1, "pageSize": 30,
                  "sortTypes": "-1", "sortColumns": "REPORT_DATE", "source": "HSF10", "client": "PC"}
        try:
            res = requests.get(url, params=params, headers=self.headers, timeout=10).json()
            data = res.get('result', {}).get('data', [])
            annual = [d for d in data if '12-31' in str(d.get('REPORT_DATE', ''))][:5]
            if not annual: return None
            roes = [d.get('ROEJQ') for d in annual if d.get('ROEJQ')]
            gms = [d.get('XSMLL') for d in annual if d.get('XSMLL')]
            rds = [d.get('RDEXPEND', 0) / max(d.get('TOTALOPERATEREVE', 1), 1) * 100 for d in annual]
            ta = annual[0].get('TOTAL_ASSETS_PK', 1)
            return {"roe_mean": np.mean(roes) if roes else 0, "roe_std": np.std(roes) if len(roes)>1 else 0,
                    "gm_mean": np.mean(gms) if gms else 0, "rd_ratio": np.mean(rds) if rds else 0, "ta_latest": ta}
        except: return None

    def _get_balance_details(self, code):
        url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        params = {"reportName": "RPT_DMSK_FN_BALANCE", "columns": "ALL",
                  "filter": f'(SECURITY_CODE="{code}")', "pageNumber": 1, "pageSize": 5,
                  "sortTypes": "-1", "sortColumns": "REPORT_DATE", "source": "HSF10", "client": "PC"}
        try:
            res = requests.get(url, params=params, headers=self.headers, timeout=10).json()
            data = res.get('result', {}).get('data', [])
            if not data: return None
            latest = data[0]
            return {"fixed_asset": latest.get('FIXED_ASSET', 0) or 0, "accounts_rece": latest.get('ACCOUNTS_RECE', 0) or 0}
        except: return None

    def diagnose(self, code):
        income = self._get_income_summary(code)
        balance = self._get_balance_details(code)
        if not income or not balance: return {"error": "数据获取失败"}
        ta = income['ta_latest']
        fa_ratio = (balance['fixed_asset'] / ta * 100) if ta > 0 and balance['fixed_asset'] else 0
        ar_ratio = (balance['accounts_rece'] / ta * 100) if ta > 0 and balance['accounts_rece'] else 0
        metrics = {"ROE均值(%)": round(income['roe_mean'], 2), "ROE波动": round(income['roe_std'], 2),
                   "毛利率(%)": round(income['gm_mean'], 2), "研发占比(%)": round(income['rd_ratio'], 2),
                   "固资占比(%)": round(fa_ratio, 2), "应收占比(%)": round(ar_ratio, 2)}
        scores = {}
        scores["项目工程型"] = (5 if ar_ratio > 10 else 0) + (3 if income['gm_mean'] < 15 else 0)
        scores["周期制造型"] = (5 if fa_ratio > 30 else 0) + (3 if income['roe_std'] > 6 else 0) + (1 if income['gm_mean'] < 30 else 0)
        scores["收租型"] = (4 if income['roe_std'] < 4 else 0) + (2 if income['gm_mean'] > 40 else 0)
        scores["消费心智型"] = (3 if income['roe_mean'] > 18 else 0) + (3 if income['roe_std'] < 5 else 0) + (2 if 25 < income['gm_mean'] < 60 else 0)
        scores["技术迭代型"] = (4 if income['rd_ratio'] > 6 else 0) + (2 if fa_ratio < 30 else 0) + (1 if income['roe_mean'] > 15 else 0)
        final_type = "未明确"
        if ar_ratio > 10 and income['gm_mean'] < 15: final_type = "项目工程型"
        elif fa_ratio > 30: final_type = "周期制造型"
        else:
            best = max(scores, key=scores.get)
            if scores[best] >= 6: final_type = best
            elif scores["收租型"] > scores["消费心智型"] and income['roe_mean'] > 20: final_type = "消费心智型(类收租)"
            elif scores["收租型"] >= 5: final_type = "收租型"
        return {"business_model": final_type, "metrics": metrics}
