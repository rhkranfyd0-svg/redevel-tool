# api_client.py — 외부 API 연동 (V-World, 국가주소 API)
# API 키 없을 경우 목업 데이터로 동작

import os
import requests
from typing import Optional

VWORLD_API_KEY = os.environ.get("VWORLD_API_KEY", "")
JUSO_API_KEY   = os.environ.get("JUSO_API_KEY", "")

# 목업 데이터 (API 키 없을 때)
MOCK_SITE_DATA = {
    "대지면적": 12000.0,
    "용도지역": "제2종일반주거지역",
    "자치구": "용산구",
    "지번": "서계동 1-1",
    "source": "mock",
}


def get_site_info(address: str) -> dict:
    """
    주소 → 대지면적·용도지역·자치구 반환
    API 키 없거나 오류 시 목업 데이터 반환
    """
    if not address or not address.strip():
        return MOCK_SITE_DATA

    # 국가주소 API (도로명주소) 호출
    if JUSO_API_KEY:
        try:
            resp = requests.get(
                "https://www.juso.go.kr/addrlink/addrLinkApi.do",
                params={
                    "confmKey": JUSO_API_KEY,
                    "currentPage": 1,
                    "countPerPage": 1,
                    "keyword": address,
                    "resultType": "json",
                },
                timeout=5,
            )
            data = resp.json()
            if data.get("results", {}).get("juso"):
                juso = data["results"]["juso"][0]
                # V-World로 용도지역 조회
                if VWORLD_API_KEY:
                    return _get_vworld_info(juso)
        except Exception:
            pass

    # V-World 단독 호출 시도
    if VWORLD_API_KEY:
        try:
            return _get_vworld_info({"roadAddrPart1": address})
        except Exception:
            pass

    # 목업 반환
    return {**MOCK_SITE_DATA, "입력주소": address}


def _get_vworld_info(juso: dict) -> dict:
    """V-World API로 토지 정보 조회"""
    addr = juso.get("roadAddrPart1", "") or juso.get("jibunAddr", "")
    resp = requests.get(
        "https://api.vworld.kr/req/address",
        params={
            "service": "address",
            "request": "getCoord",
            "version": "2.0",
            "crs": "epsg:4326",
            "address": addr,
            "type": "road",
            "key": VWORLD_API_KEY,
            "format": "json",
        },
        timeout=5,
    )
    data = resp.json()
    result = data.get("response", {}).get("result", {})
    point = result.get("point", {})

    return {
        "대지면적": 5000.0,      # 필지 면적은 별도 API 필요 (개략값)
        "용도지역": "제2종일반주거지역",  # 용도지역도 별도 API 필요
        "자치구": _extract_district(addr),
        "좌표X": point.get("x", ""),
        "좌표Y": point.get("y", ""),
        "입력주소": addr,
        "source": "vworld",
    }


def _extract_district(address: str) -> str:
    """주소 문자열에서 자치구 추출"""
    districts = [
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구",
        "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구",
        "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구",
        "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구",
    ]
    for d in districts:
        if d in address:
            return d
    return "용산구"  # 기본값
