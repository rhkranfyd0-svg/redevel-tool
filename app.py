# app.py — 서울시 정비사업 기초 규모·사업성 자동 분석 툴
# 실행: streamlit run app.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from reference import ZONING_LIST, DISTRICT_LIST, DISTRICT_PRICE
from calculator import SiteInput, calculate_scale, calculate_cost, fmt_man, fmt_area
from api_client import get_site_info
from llm_client import generate_all_checklists, PHASE_CONFIG
from facilities import check_all, to_dataframe, summary_stats

# ── 페이지 설정 ────────────────────────────────────────────────
st.set_page_config(
    page_title="정비사업 규모·사업성 분석",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .metric-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 4px 0;
  }
  .warning-box {
    background: #fff8e1;
    border-left: 4px solid #ffc107;
    padding: 12px 16px;
    border-radius: 4px;
    font-size: 13px;
    color: #555;
    margin: 8px 0;
  }
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ───────────────────────────────────────────
if "checklists" not in st.session_state:
    st.session_state.checklists = None
if "last_inputs" not in st.session_state:
    st.session_state.last_inputs = {}


# ── 사이드바 입력 ──────────────────────────────────────────────
with st.sidebar:
    st.title("🏙️ 사업 조건 입력")

    st.subheader("📍 대지 정보")
    address = st.text_input(
        "주소 입력",
        placeholder="예: 서울특별시 용산구 서계동 1-1",
        help="도로명 주소 또는 지번 주소 입력. API 키 미설정 시 목업 데이터로 동작."
    )
    use_api = st.checkbox("주소 API로 자동 조회", value=False,
                          help="V-World API 키 설정 시 대지면적·용도지역 자동 조회")

    st.divider()
    st.subheader("🗺️ 용도지역 / 자치구")

    zoning = st.selectbox("용도지역", ZONING_LIST, index=1)
    district = st.selectbox("자치구", DISTRICT_LIST,
                             index=DISTRICT_LIST.index("용산구"))

    st.divider()
    st.subheader("📐 대지·세대 조건")

    site_area = st.number_input(
        "대지면적 (㎡)", min_value=500.0, max_value=100000.0,
        value=12000.0, step=100.0
    )
    non_res_ratio = st.slider(
        "비주거 비율 (%)", min_value=0, max_value=30, value=10
    ) / 100

    st.subheader("🏠 세대 구성 비율")
    col1, col2, col3 = st.columns(3)
    with col1:
        ratio_small = st.number_input("소형 59㎡ (%)", 0, 100, 20)
    with col2:
        ratio_mid   = st.number_input("국민 84㎡ (%)", 0, 100, 60)
    with col3:
        ratio_large = st.number_input("중대형 114㎡ (%)", 0, 100, 20)

    total_ratio = ratio_small + ratio_mid + ratio_large
    if total_ratio != 100:
        st.warning(f"세대 비율 합계: {total_ratio}% (100%이어야 함)")

    st.divider()
    st.subheader("💰 공사비 단가 (만원/㎡)")
    cost_above = st.number_input("지상층", 200, 500, 300, step=10)
    cost_below  = st.number_input("지하층", 300, 600, 380, step=10)

    run_btn = st.button("🔍 분석 실행", use_container_width=True, type="primary")

# ── 계산 실행 ─────────────────────────────────────────────────
if run_btn and total_ratio == 100:
    inp = SiteInput(
        site_area=site_area,
        zoning=zoning,
        district=district,
        non_residential_ratio=non_res_ratio,
        type_ratio_small=ratio_small / 100,
        type_ratio_mid=ratio_mid / 100,
        type_ratio_large=ratio_large / 100,
        cost_above_ground=float(cost_above),
        cost_underground=float(cost_below),
    )
    scale = calculate_scale(inp)
    cost  = calculate_cost(inp, scale)
    st.session_state.inp   = inp
    st.session_state.scale = scale
    st.session_state.cost  = cost
    st.session_state.checklists = None  # 체크리스트 초기화

# ── 결과 표시 ─────────────────────────────────────────────────
if "scale" in st.session_state:
    inp   = st.session_state.inp
    scale = st.session_state.scale
    cost  = st.session_state.cost

    st.title(f"🏙️ {inp.zoning} — {inp.district} 정비사업 분석")

    st.markdown("""
    <div class="warning-box">
    ⚠️ 본 결과는 초기 기획 참고용이며 법적 효력이 없습니다.
    분양가·공사비는 개략값이며, 실제 사업성은 이주비·금융비용·부담금 등 포함 시 달라질 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📐 규모 산출", "💰 사업성", "📋 법규 체크리스트", "🏢 부대시설"])

    # ─── TAB 1: 규모 산출 ─────────────────────────────────────
    with tab1:
        st.subheader("규모 산출 결과")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("법적상한용적률", f"{scale.far_limit}%")
        c2.metric("지상 총 연면적", fmt_area(scale.gfa_total))
        c3.metric("총 세대수", f"{scale.total_units}세대")
        c4.metric("법정 주차대수", f"{scale.parking_required}대")

        st.divider()
        st.subheader("세대 구성")
        unit_df = pd.DataFrame(
            [(k, v, f"{v / scale.total_units * 100:.1f}%") for k, v in scale.units.items()],
            columns=["유형", "세대수", "비율"]
        )
        st.dataframe(unit_df, hide_index=True, use_container_width=True)

        # 파이차트
        fig = go.Figure(go.Pie(
            labels=list(scale.units.keys()),
            values=list(scale.units.values()),
            hole=0.4,
        ))
        fig.update_layout(title="세대 구성 비율", height=300, margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # ─── TAB 2: 사업성 ────────────────────────────────────────
    with tab2:
        st.subheader("사업성 산출 결과")
        c1, c2, c3 = st.columns(3)
        c1.metric("총 공사비", fmt_man(cost.construction_total))
        c2.metric("총 분양수입", fmt_man(cost.sales_total))
        profit_label = "개략 수익 (공사비 기준)"
        profit_delta = "이주비·금융비용 미포함"
        c3.metric(profit_label, fmt_man(cost.profit_gross), profit_delta)

        st.caption(f"적용 분양가: {cost.price_per_sqm:,} 만원/㎡ ({inp.district} 기준)")

        st.divider()
        # 공사비 구성 바차트
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="지상 공사비", x=["공사비"], y=[cost.construction_above / 1_0000]))
        fig2.add_trace(go.Bar(name="지하 공사비", x=["공사비"], y=[cost.construction_below / 1_0000]))
        fig2.update_layout(
            barmode="stack", title="공사비 구성 (억원)", height=300,
            yaxis_title="억원", margin=dict(t=40, b=0)
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 분양수입 유형별
        sales_df = pd.DataFrame(
            [(k, fmt_man(v)) for k, v in cost.sales_by_type.items()],
            columns=["유형", "분양수입"]
        )
        st.dataframe(sales_df, hide_index=True, use_container_width=True)

    # ─── TAB 3: LLM 법규 체크리스트 ──────────────────────────
    with tab3:
        st.subheader(f"단계별 법규 검토 체크리스트 — {inp.zoning}")
        st.caption("Claude API 기반 자동 생성 | AI 오류 가능성 있음 — 전문가 최종 검토 필수")

        c1, c2, c3 = st.columns(3)
        c1.metric("용적률 판정", f"{scale.far_limit}%", "법적상한 적용 ✅")
        c2.metric("대지면적", f"{inp.site_area:,.0f}㎡", "입력값")
        c3.metric("주차 판정", f"{scale.parking_required}대", "산출값")

        st.divider()
        if st.session_state.checklists is None:
            with st.spinner("3단계 체크리스트 생성 중... (약 10~30초)"):
                st.session_state.checklists = generate_all_checklists(
                    zoning=inp.zoning,
                    site_area=inp.site_area,
                    far_applied=scale.far_limit,
                    far_limit=scale.far_limit,
                    bcr_limit=scale.bcr_limit,
                    total_units=scale.total_units,
                    parking_required=scale.parking_required,
                    gfa_total=scale.gfa_total,
                    type_ratio_small=inp.type_ratio_small,
                )

        checklists = st.session_state.checklists
        for phase_key, phase_info in PHASE_CONFIG.items():
            with st.expander(phase_info["title"], expanded=(phase_key == "phase1")):
                st.markdown(checklists.get(phase_key, "생성 실패"))

    # ─── TAB 4: 부대시설 체크리스트 ──────────────────────────
    with tab4:
        st.subheader("법정 부대시설 체크리스트")
        st.caption("주택건설기준등에관한규정 + 서울특별시 주택조례 기준 (2024)")

        checks = check_all(scale.total_units, inp.site_area, inp.zoning)
        stats  = summary_stats(checks)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("전체 항목", f"{stats['total']}개")
        c2.metric("✅ 충족", f"{stats['ok']}개")
        c3.metric("⚠️ 확인 필요", f"{stats['warn']}개")
        c4.metric("❌ 위반", f"{stats['fail']}개")

        st.divider()
        df = to_dataframe(checks)
        st.dataframe(df, hide_index=True, use_container_width=True)

        if stats["warn"] > 0 or stats["fail"] > 0:
            st.markdown("""
            <div class="warning-box">
            ⚠️ 확인 필요 항목이 있습니다. 실제 설계 단계에서 전문가 검토가 필요합니다.
            </div>
            """, unsafe_allow_html=True)

else:
    # 초기 화면
    st.title("🏙️ 서울시 정비사업 기초 분석 툴")
    st.markdown("""
    ### 사용 방법
    1. 왼쪽 사이드바에서 **사업 조건을 입력**하세요
    2. **분석 실행** 버튼을 클릭하세요
    3. **규모 산출 / 사업성 / 법규 체크리스트** 탭에서 결과를 확인하세요

    ---

    ### 분석 내용
    | 탭 | 내용 |
    |---|---|
    | 📐 규모 산출 | 용적률·연면적·세대수·주차대수 자동 산정 |
    | 💰 사업성 | 총 공사비·분양수입·개략 수익 산출 |
    | 📋 법규 체크리스트 | Claude AI 기반 3단계 법규 자동 검토 |
    | 🏢 부대시설 | 법정 부대시설 의무 항목 자동 체크 |

    ---

    > 본 툴은 초기 기획 단계 참고용입니다. 법적 효력이 없으며 전문가 검토가 필요합니다.
    """)
