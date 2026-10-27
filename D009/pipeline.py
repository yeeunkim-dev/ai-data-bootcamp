# 시나리오 2 — 빵셀러 정제 파이프라인 모듈
import pandas as pd

def b_dedup(df): return df.drop_duplicates().reset_index(drop=True)                 # 완전 중복 제거
def b_strip_store(df): return df.assign(store_id=df["store_id"].str.strip())        # 매장 ID 공백 제거
def b_unify_item(df): return df.assign(item=df["item"].replace({"케익": "케이크"}))     # 표기 통일
def b_parse_date(df): return df.assign(
    date=pd.to_datetime(df["date_str"], format="mixed", errors="coerce")
).drop(columns=["date_str"])                                                        # 날짜 포맷 통일
def b_drop_refund(df): return df[(df["revenue"] >= 0) | df["revenue"].isna()]   # 환불(음수)만 제외, 결측은 다음 단계에서 처리
def b_drop_missing_revenue(df): return df.dropna(subset=["revenue"])          # 매출 결측 제거

def full_pipeline(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # 원본 데이터 -> (정제 데이터, 환불 데이터)
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