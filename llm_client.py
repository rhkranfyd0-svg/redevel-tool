# llm_client.py — Claude API 연동 법규 체크리스트 생성
# Anthropic Claude API 사용 (API 키 없을 시 목업 반환)

import os
import anthropic
from reference import get_regulation_text

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# 단계별 체크리스트 프롬프트 설정
PHASE_CONFIG = {
    "phase1": {"title": "단계 1: 기획·규모 검토", "focus": "용적률, 건폐율, 세대수, 용도 적합성"},
    "phase2": {"title": "단계 2: 주요 법규 준수 여부", "focus": "주차, 조경, 공개공지, 임대주택 의무"},
    "phase3": {"title": "단계 3: 사업성 리스크", "focus": "부담금, 기반시설 기여, 환경영향평가 필요 여부"},
}

MOCK_CHECKLIST = """
| 항목 | 기준 | 검토 결과 | 비고 |
|------|------|-----------|------|
| 용적률 적용 | 법적상한용적률 이하 | ✅ 충족 | 인센티브 조건 확인 필요 |
| 건폐율 | 60% 이하 | ✅ 충족 | - |
| 최소 대지면적 | 정비구역 지정 요건 충족 | ⚠️ 확인 필요 | 구역 지정 여부 확인 |
| 임대주택 의무 | 증가 용적률의 50% | ✅ 충족 | 비율 산정 필요 |
| 기반시설 기여 | 지구단위계획 조건 | ⚠️ 확인 필요 | 도로·공원 기여율 검토 |

*API 키 미설정 상태 — 목업 데이터입니다.*
"""


def generate_checklist(
    phase: str,
    zoning: str,
    site_area: float,
    far_applied: float,
    far_limit: float,
    bcr_limit: float,
    total_units: int,
    parking_required: int,
    gfa_total: float,
    type_ratio_small: float,
) -> str:
    """단일 단계 법규 체크리스트 생성"""
    if not ANTHROPIC_API_KEY:
        return MOCK_CHECKLIST

    regulation_text = get_regulation_text(zoning)
    phase_info = PHASE_CONFIG.get(phase, PHASE_CONFIG["phase1"])

    system_prompt = f"""당신은 서울시 정비사업 전문 건축·법규 검토 전문가입니다.
아래 조례 조항을 기반으로 입력된 사업 조건에 대한 법규 검토 체크리스트를 작성하세요.

{regulation_text}

출력 형식:
- 마크다운 표 형식 (항목 | 기준 | 검토 결과 | 비고)
- 검토 결과: ✅ 충족, ⚠️ 확인 필요, ❌ 위반 중 하나
- 각 항목에 근거 조항과 실무적 주의사항 포함
- 전문 용어는 괄호로 설명 추가
- 결과는 반드시 한국어로 작성
- 집중 검토 항목: {phase_info['focus']}"""

    user_prompt = f"""다음 사업 조건에 대해 "{phase_info['title']}" 체크리스트를 작성해주세요.

- 용도지역: {zoning}
- 대지면적: {site_area:,.1f} ㎡
- 적용 용적률: {far_applied}%
- 법적상한용적률: {far_limit}%
- 건폐율 상한: {bcr_limit}%
- 총 세대수: {total_units}세대
- 법정 주차대수: {parking_required}대
- 지상 총 연면적: {gfa_total:,.1f} ㎡
- 소형세대(59㎡) 비율: {int(type_ratio_small*100)}%"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )
        return message.content[0].text
    except Exception as e:
        return f"⚠️ API 호출 오류: {e}\n\n{MOCK_CHECKLIST}"


def generate_all_checklists(**kwargs) -> dict:
    """3단계 체크리스트 일괄 생성"""
    results = {}
    for phase in ["phase1", "phase2", "phase3"]:
        results[phase] = generate_checklist(phase=phase, **kwargs)
    return results
