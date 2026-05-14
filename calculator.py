# calculator.py — 규모·사업성 계산 엔진

from dataclasses import dataclass, field
from typing import Dict
from reference import ZONING, UNIT_TYPES, DISTRICT_PRICE


@dataclass
class SiteInput:
    """사용자 입력값 + API 수집값 통합 모델"""
    site_area: float            # 대지면적 (㎡)
    zoning: str                 # 용도지역명
    district: str               # 자치구
    non_residential_ratio: float = 0.10   # 비주거 비율 (0.0~0.30)
    type_ratio_small: float  = 0.20       # 소형(59㎡) 비율
    type_ratio_mid: float    = 0.60       # 국민(84㎡) 비율
    type_ratio_large: float  = 0.20       # 중대형(114㎡) 비율
    cost_above_ground: float = 300.0      # 지상 공사비 단가 (만원/㎡)
    cost_underground: float  = 380.0      # 지하 공사비 단가 (만원/㎡)


@dataclass
class ScaleResult:
    """규모 산출 결과"""
    far_limit: float
    bcr_limit: float
    gfa_total: float
    gfa_residential: float
    gfa_underground: float
    units: Dict[str, int] = field(default_factory=dict)
    total_units: int = 0
    parking_required: int = 0


@dataclass
class CostResult:
    """사업성 산출 결과"""
    construction_above: float
    construction_below: float
    construction_total: float
    sales_by_type: Dict[str, float] = field(default_factory=dict)
    sales_total: float = 0.0
    profit_gross: float = 0.0
    price_per_sqm: float = 0.0


def calculate_scale(inp: SiteInput) -> ScaleResult:
    """규모 산출 메인 함수"""
    zoning_data = ZONING.get(inp.zoning, ZONING["제2종일반주거지역"])
    far_limit = zoning_data["상한용적률"]
    bcr_limit = zoning_data["건폐율"]

    # 지상 연면적
    gfa_total = inp.site_area * far_limit / 100
    gfa_residential = gfa_total * (1 - inp.non_residential_ratio)

    # 지하주차장 면적 (세대당 약 30㎡ 가정)
    # 먼저 세대수를 추정해서 역산
    avg_unit_area = (
        59  * inp.type_ratio_small +
        84  * inp.type_ratio_mid +
        114 * inp.type_ratio_large
    ) * 1.25  # 공급면적 환산

    estimated_units = int(gfa_residential / avg_unit_area) if avg_unit_area > 0 else 0
    gfa_underground = estimated_units * 30.0

    # 세대수 계산
    units = {}
    unit_list = [
        ("소형(59㎡)",    inp.type_ratio_small,  59,  1.25),
        ("국민(84㎡)",    inp.type_ratio_mid,    84,  1.25),
        ("중대형(114㎡)", inp.type_ratio_large, 114,  1.25),
    ]
    for name, ratio, exclusive, coeff in unit_list:
        supply_area = exclusive * coeff
        count = int(gfa_residential * ratio / supply_area) if supply_area > 0 else 0
        units[name] = count

    total_units = sum(units.values())

    # 법정 주차대수 (전용 60㎡ 초과: 1대/세대, 60㎡ 이하: 0.7대/세대)
    small_units = units.get("소형(59㎡)", 0)
    other_units = total_units - small_units
    parking_required = int(small_units * 0.7 + other_units * 1.0)

    return ScaleResult(
        far_limit=far_limit,
        bcr_limit=bcr_limit,
        gfa_total=gfa_total,
        gfa_residential=gfa_residential,
        gfa_underground=gfa_underground,
        units=units,
        total_units=total_units,
        parking_required=parking_required,
    )


def calculate_cost(inp: SiteInput, scale: ScaleResult) -> CostResult:
    """사업성 산출 메인 함수"""
    # 공사비
    construction_above = scale.gfa_total * inp.cost_above_ground
    construction_below = scale.gfa_underground * inp.cost_underground
    construction_total = construction_above + construction_below

    # 분양 단가 (자치구별 분양가)
    price_per_sqm = DISTRICT_PRICE.get(inp.district, 900)

    # 세대별 분양수입
    sales_by_type = {}
    unit_specs = {
        "소형(59㎡)":    {"전용": 59,  "공급계수": 1.25},
        "국민(84㎡)":    {"전용": 84,  "공급계수": 1.25},
        "중대형(114㎡)": {"전용": 114, "공급계수": 1.25},
    }
    sales_total = 0.0
    for name, count in scale.units.items():
        spec = unit_specs.get(name, {"전용": 84, "공급계수": 1.25})
        supply_area = spec["전용"] * spec["공급계수"]
        revenue = count * supply_area * price_per_sqm
        sales_by_type[name] = revenue
        sales_total += revenue

    profit_gross = sales_total - construction_total

    return CostResult(
        construction_above=construction_above,
        construction_below=construction_below,
        construction_total=construction_total,
        sales_by_type=sales_by_type,
        sales_total=sales_total,
        profit_gross=profit_gross,
        price_per_sqm=price_per_sqm,
    )


def fmt_man(value: float) -> str:
    """만원 → '억원' 또는 '조원' 단위 표기"""
    if abs(value) >= 1_0000_0000:
        return f"{value / 1_0000_0000:,.2f} 조원"
    elif abs(value) >= 1_0000:
        return f"{value / 1_0000:,.1f} 억원"
    else:
        return f"{value:,.0f} 만원"


def fmt_area(value: float) -> str:
    """면적 포맷팅"""
    return f"{value:,.1f} ㎡"
