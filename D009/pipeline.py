# 시나리오 2 — 빵셀러 정제 파이프라인 모듈
import pandas as pd

decisions = []

def log_decision(step: str, action: str, reason: str, result: str):
    decisions.append({"step": step, "action": action, "reason": reason, "result": result})

def b_dedup(df): 
    out = df.drop_duplicates().reset_index(drop=True)
    n = len(df) - len(out)
    log_decision(
        "1. 중복 제거",
        "drop_duplicates()로 완전 중복 행 제거",
        "모든 컬럼 값이 같은 행은 같은 거래의 중복 입력으로 간주 (값 종류가 적어 우연히 겹친 행일 가능성은 한계로 남김)",
        f"{n}건 제거"
    )
    return out

def b_strip_store(df): 
    out = df.assign(store_id=df["store_id"].str.strip())
    n_space = (df["store_id"] != df["store_id"].str.strip()).sum()
    log_decision(
        "2. store_id 정리",
        "str.strip()으로 앞뒤 공백 제거",
        "' S01 '과 'S01'은 같은 매장인데 groupby에서 따로 집계됨",
        f"{n_space}건 정리 (매장 7→6종)",
    )
    return out

def b_unify_item(df): 
    out = df.assign(item=df["item"].replace({"케익": "케이크"}))
    n_cake = (df["item"] == "케익").sum()
    log_decision(
        "3. 상품명 통일",
        "'케익' → '케이크' 치환",
        "같은 상품의 표기 차이로 상품별 KPI가 둘로 쪼개짐",
        f"{n_cake}건 변환 (상품 6→5종)",
    )
    return out

def b_parse_date(df): 
    out = df.assign(
        date=pd.to_datetime(df["date_str"], format="mixed", errors="coerce")
    ).drop(columns=["date_str"])
    n_nat = out["date"].isna().sum()
    log_decision(
        "4. 날짜 파싱",
        "pd.to_datetime(format='mixed')로 변환 후 date_str 삭제",
        "'-', '/', 구분자 없음 3가지 포맷이 섞여 월별 집계 불가",
        f"파싱 실패 {n_nat}건",
    )   
    return out

# 환불(음수)만 제외, 결측은 다음 단계에서 처리
def b_drop_refund(df): 
    out = df[(df["revenue"] >= 0) | df["revenue"].isna()]
    n_refund = (df["revenue"] < 0).sum()
    log_decision(
        "5. 환불 분리",
        "revenue < 0 행을 refunds_bakery에 보관 후 본 분석에서 제외",
        "음수가 섞이면 매출 KPI가 왜곡됨, 삭제 대신 보관해 원인 분석에 활용",
        f"{n_refund}건 분리",       
    )
    return out

# 매출 결측 제거
def b_drop_missing_revenue(df): 
    out = df.dropna(subset=["revenue"])
    n_missing = df["revenue"].isna().sum()
    log_decision(
        "6. 결측 제거",
        "revenue 결측 행 drop",
        "결측률 약 3%로 낮고, 평균 등으로 채우면 없는 매출이 생겨 KPI 왜곡",
        f"{n_missing}건 제거 (원본 60건 중 2건은 중복 제거 단계에서 이미 제거)",
    )
    return out


def full_pipeline(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # 원본 데이터 -> (정제 데이터, 환불 데이터)
    decisions.clear()
    refunds = df[df["revenue"] < 0].copy()    # 환불은 따로 보관

    clean = (
        df
        .pipe(b_dedup)
        .pipe(b_strip_store)
        .pipe(b_unify_item)
        .pipe(b_parse_date)
        .pipe(b_drop_refund)
        .pipe(b_drop_missing_revenue)
        .reset_index(drop=True)
    )
    return clean, refunds

