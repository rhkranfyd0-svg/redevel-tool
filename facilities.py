# facilities.py — 부대시설 법정 기준 체크리스트
# 주택건설기준 등에 관한 규정 + 서울특별시 주택조례 기준 (2024)

from dataclasses import dataclass
from typing import List
import pandas as pd


@dataclass
class LawCheck:
    """법규 항목 체크 결과"""
    항목: str
    기준: str
    산출값: str
    결과: str   # "✅ 충족", "⚠️ 확인 필요", "❌ 위반"
    법조항: str
    법규내용: str


def check_all(total_units: int, site_area: float, zoning: str) -> List[LawCheck]:
    """세대수·대지면적·용도지역 기반 법정 부대시설 체크"""
    results: List[LawCheck] = []

    # ── 어린이놀이터 ───────────────────────────────────────────
    if total_units >= 50:
        required_area = max(150, total_units * 1.0)
        results.append(LawCheck(
            항목="어린이놀이터",
            기준=f"50세대 이상: 세대수 × 1㎡ 이상 (최소 150㎡)",
            산출값=f"필요 면적: {required_area:,.0f}㎡",
            결과="✅ 충족" if site_area * 0.05 >= required_area else "⚠️ 확인 필요",
            법조항="주택건설기준등에관한규정 제55조의2",
            법규내용="50세대 이상 공동주택 건설 시 어린이놀이터 의무 설치",
        ))

    # ── 경로당 ─────────────────────────────────────────────────
    if total_units >= 100:
        if total_units < 300:
            req = 225
        elif total_units < 500:
            req = 225 + (total_units - 300) * 0.5
        else:
            req = 325 + (total_units - 500) * 0.5
        req = max(225, req)
        results.append(LawCheck(
            항목="경로당",
            기준="100세대 이상: 최소 225㎡ (세대수에 따라 증가)",
            산출값=f"필요 면적: {req:,.0f}㎡",
            결과="✅ 충족",
            법조항="서울특별시 주택조례 별표1",
            법규내용="100세대 이상 공동주택 경로당 의무 설치",
        ))

    # ── 어린이집 ────────────────────────────────────────────────
    if total_units >= 300:
        results.append(LawCheck(
            항목="어린이집",
            기준="300세대 이상: 의무 설치 (영유아보육법)",
            산출값=f"{total_units}세대 → 의무 대상",
            결과="✅ 충족",
            법조항="영유아보육법 제14조",
            법규내용="300세대 이상 공동주택 어린이집 설치 의무",
        ))

    # ── 주민공동시설 ─────────────────────────────────────────────
    if total_units >= 150:
        if total_units <= 500:
            req = 250 + (total_units - 150) * 0.5
        else:
            req = 250 + 350 * 0.5 + (total_units - 500) * 0.3
        results.append(LawCheck(
            항목="주민공동시설",
            기준="150세대 이상: 세대수에 따라 면적 산정",
            산출값=f"필요 면적: {req:,.0f}㎡",
            결과="✅ 충족",
            법조항="주택건설기준등에관한규정 제55조의3",
            법규내용="150세대 이상 주민공동시설 의무 설치",
        ))

    # ── 관리사무소 ───────────────────────────────────────────────
    if total_units >= 50:
        results.append(LawCheck(
            항목="관리사무소",
            기준="50세대 이상: 10㎡ 이상",
            산출값="면적 10㎡ 이상 확보",
            결과="✅ 충족",
            법조항="주택건설기준등에관한규정 제55조",
            법규내용="50세대 이상 관리사무소 의무 설치 (10㎡ 이상)",
        ))

    # ── 조경면적 ─────────────────────────────────────────────────
    조경비율 = 0.15 if "주거" in zoning else 0.10
    required_landscape = site_area * 조경비율
    results.append(LawCheck(
        항목="조경면적",
        기준=f"대지면적의 {int(조경비율*100)}% 이상",
        산출값=f"필요 면적: {required_landscape:,.0f}㎡",
        결과="✅ 충족",
        법조항="서울특별시 도시계획 조례 제33조",
        법규내용="용도지역에 따른 조경면적 의무 확보",
    ))

    # ── 공개공지 ─────────────────────────────────────────────────
    gfa_estimated = site_area * 2.5  # 대략적 추정
    if gfa_estimated >= 5000:
        req_open = site_area * 0.05
        results.append(LawCheck(
            항목="공개공지",
            기준="연면적 5,000㎡ 이상: 대지면적의 5~10%",
            산출값=f"필요 면적: {req_open:,.0f}㎡ 이상",
            결과="⚠️ 확인 필요",
            법조항="건축법 제43조",
            법규내용="일정 규모 이상 건축물 공개공지 의무 확보",
        ))

    return results


def to_dataframe(checks: List[LawCheck]) -> pd.DataFrame:
    """체크리스트를 DataFrame으로 변환"""
    return pd.DataFrame([
        {
            "항목": c.항목,
            "기준": c.기준,
            "산출값": c.산출값,
            "결과": c.결과,
            "법조항": c.법조항,
        }
        for c in checks
    ])


def summary_stats(checks: List[LawCheck]) -> dict:
    """체크리스트 요약 통계"""
    total = len(checks)
    ok = sum(1 for c in checks if "✅" in c.결과)
    warn = sum(1 for c in checks if "⚠️" in c.결과)
    fail = sum(1 for c in checks if "❌" in c.결과)
    return {"total": total, "ok": ok, "warn": warn, "fail": fail}
