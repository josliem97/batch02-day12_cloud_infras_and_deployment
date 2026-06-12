from __future__ import annotations

import json
from typing import Any

from tools._shared import ROOT, err

FOOD_DATA_FILE = ROOT / "data" / "dataset_food.json"

def _load_food_data() -> list[dict[str, Any]]:
    try:
        with FOOD_DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Không tìm thấy file dữ liệu tại {FOOD_DATA_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: File dữ liệu bị lỗi định dạng JSON. Chi tiết: {e}")
        return []

def _check_allergy(thanh_phan_mon: list[str], danh_sach_di_ung: list[str]) -> bool:
    if not danh_sach_di_ung:
        return False
    tp_lower = [tp.lower() for tp in thanh_phan_mon]
    du_lower = [du.lower() for du in danh_sach_di_ung]
    
    for du in du_lower:
        if any(du in tp for tp in tp_lower):
            return True
    return False

def _calculate_match_score(mon: dict[str, Any], loai_mong_muon: str, vi_mong_muon: str) -> int:
    score = 0
    if loai_mong_muon and loai_mong_muon.lower() in mon["loai"].lower():
        score += 1
    if vi_mong_muon and vi_mong_muon.lower() in mon["vi"].lower():
        score += 1
    return score

def filter_and_recommend_food(
    loai_mon: str = "", 
    vi: str = "", 
    di_ung: list[str] | None = None, 
    ban_kinh_km: float = 3.0,
    ngan_sach: int = 0
) -> dict[str, Any]:
    try:
        food_dataset = _load_food_data()
        if not food_dataset:
            return {"error": "Hệ thống hiện không có dữ liệu món ăn."}

        di_ung_list = di_ung or []
        filtered_foods = []

        for mon in food_dataset:
            if mon["khoang_cach_km"] > ban_kinh_km:
                continue
            if ngan_sach > 0 and mon["gia"] > ngan_sach:
                continue
            if _check_allergy(mon["thanh_phan"], di_ung_list):
                continue
                
            filtered_foods.append(mon)

        scored_foods = []
        for mon in filtered_foods:
            score = _calculate_match_score(mon, loai_mon, vi)
            mon_info = mon.copy()
            mon_info["match_score"] = score
            scored_foods.append(mon_info)

        scored_foods.sort(key=lambda x: x["match_score"], reverse=True)
        top_3_foods = scored_foods[:3]

        items = []
        for mon in top_3_foods:
            items.append({
                "id": mon["id"],
                "title": mon["name"],
                "loai": mon["loai"],
                "vi": mon["vi"],
                "gia": mon["gia"],
                "thanh_phan": mon["thanh_phan"],
                "khoang_cach_km": mon["khoang_cach_km"],
                "ly_do_goi_y": f"Khớp {mon['match_score']}/2 tiêu chí của bạn. An toàn dị ứng. Cách {mon['khoang_cach_km']}km." 
            })

        return {
            "tool": "filter_and_recommend_food",
            "total_matches_found": len(scored_foods),
            "items_returned": len(items),
            "applied_filters": {
                "max_km": ban_kinh_km,
                "allergies": di_ung_list,
                "max_price": ngan_sach
            },
            "items": items,
        }

    except Exception as exc:
        return err("filter_and_recommend_food", exc)
