import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="Supabase 한글 CRUD 대시보드",
    page_icon="🗄️",
    layout="wide",
)

SCHEMA_SNAPSHOT = "2026-09-11"
CHART_ROW_LIMIT = 5000

DEFAULT_SUPABASE_URL = "https://lrlqgmeghgmowypenfyp.supabase.co"
DEFAULT_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_EHqRMCLwHWle7a6jdrPRWQ_HSSI4MfW"

TABLE_LABELS = {
    "branches": "지점",
    "members": "조합원",
    "deposit_accounts": "예금 계좌",
    "loans": "대출",
    "transactions": "거래 내역",
    "financial_institution_deposit_rates": "금융기관 예금금리",
}

COLUMN_LABELS = {
    "branch_id": "지점 번호",
    "branch_name": "지점명",
    "region": "지역",
    "manager_name": "지점장명",
    "member_id": "조합원 번호",
    "name": "조합원명",
    "birth_date": "생년월일",
    "gender": "성별",
    "join_date": "가입일",
    "phone": "전화번호",
    "account_id": "계좌 번호",
    "account_type": "계좌 종류",
    "open_date": "개설일",
    "balance": "잔액",
    "interest_rate": "금리(%)",
    "loan_id": "대출 번호",
    "loan_type": "대출 종류",
    "loan_amount": "대출 금액",
    "start_date": "대출 시작일",
    "due_date": "만기일",
    "status": "상태",
    "transaction_id": "거래 번호",
    "transaction_date": "거래 일시",
    "transaction_type": "거래 종류",
    "amount": "거래 금액",
    "balance_after": "거래 후 잔액",
    "id": "번호",
    "financial_institution_name": "금융기관명",
    "region_category": "권역 분류",
    "product_name": "상품명",
    "base_rate": "기본금리(%)",
    "maximum_preferential_rate": "최고우대금리(%)",
    "preferential_conditions": "주요 우대조건",
    "source_url": "출처 URL",
    "as_of_date": "기준일",
    "created_at": "등록일시",
}

TABLES: dict[str, dict[str, Any]] = {
    "branches": {
        "pk": "branch_id",
        "rls": False,
        "columns": {
            "branch_id": {"type": "integer", "nullable": False},
            "branch_name": {"type": "text", "nullable": False},
            "region": {"type": "text", "nullable": False},
            "manager_name": {"type": "text", "nullable": False},
        },
    },
    "members": {
        "pk": "member_id",
        "rls": False,
        "columns": {
            "member_id": {"type": "integer", "nullable": False},
            "name": {"type": "text", "nullable": False},
            "birth_date": {"type": "date", "nullable": False},
            "gender": {"type": "text", "nullable": False},
            "join_date": {"type": "date", "nullable": False},
            "branch_id": {"type": "integer", "nullable": False},
            "phone": {"type": "text", "nullable": False},
        },
    },
    "deposit_accounts": {
        "pk": "account_id",
        "rls": False,
        "columns": {
            "account_id": {"type": "integer", "nullable": False},
            "member_id": {"type": "integer", "nullable": False},
            "branch_id": {"type": "integer", "nullable": False},
            "account_type": {"type": "text", "nullable": False},
            "open_date": {"type": "date", "nullable": False},
            "balance": {"type": "numeric", "nullable": False},
            "interest_rate": {"type": "numeric", "nullable": False},
        },
    },
    "loans": {
        "pk": "loan_id",
        "rls": False,
        "columns": {
            "loan_id": {"type": "integer", "nullable": False},
            "member_id": {"type": "integer", "nullable": False},
            "branch_id": {"type": "integer", "nullable": False},
            "loan_type": {"type": "text", "nullable": False},
            "loan_amount": {"type": "numeric", "nullable": False},
            "interest_rate": {"type": "numeric", "nullable": False},
            "start_date": {"type": "date", "nullable": False},
            "due_date": {"type": "date", "nullable": False},
            "status": {"type": "text", "nullable": False},
        },
    },
    "transactions": {
        "pk": "transaction_id",
        "rls": False,
        "columns": {
            "transaction_id": {"type": "integer", "nullable": False},
            "account_id": {"type": "integer", "nullable": False},
            "transaction_date": {"type": "timestamp", "nullable": False},
            "transaction_type": {"type": "text", "nullable": False},
            "amount": {"type": "numeric", "nullable": False},
            "balance_after": {"type": "numeric", "nullable": False},
        },
    },
    "financial_institution_deposit_rates": {
        "pk": "id",
        "rls": True,
        "columns": {
            "id": {"type": "integer", "nullable": False, "generated": True},
            "financial_institution_name": {"type": "text", "nullable": False},
            "region_category": {"type": "text", "nullable": False},
            "product_name": {"type": "text", "nullable": False},
            "base_rate": {"type": "numeric", "nullable": False},
            "maximum_preferential_rate": {"type": "numeric", "nullable": False},
            "preferential_conditions": {"type": "text", "nullable": True},
            "source_url": {"type": "text", "nullable": False},
            "as_of_date": {"type": "date", "nullable": False},
            "created_at": {"type": "timestamp", "nullable": False, "default": True},
        },
    },
}


def table_label(table_name: str) -> str:
    return TABLE_LABELS.get(table_name, table_name)


def column_label(column_name: str) -> str:
    return COLUMN_LABELS.get(column_name, column_name)


def configured_value(*names: str) -> str:
    for name in names:
        try:
            value = st.secrets.get(name, "")
            if value:
                return str(value)
        except Exception:
            pass
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value:
        return date.fromisoformat(str(value)[:10])
    return date.today()


def parse_datetime_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def scalar_input(
    column_name: str,
    meta: dict[str, Any],
    key: str,
    current: Any = None,
) -> Any:
    dtype = meta["type"]
    label = column_label(column_name)

    if dtype == "integer":
        default = int(current) if current not in (None, "") else 0
        return int(st.number_input(label, value=default, step=1, key=key))

    if dtype == "numeric":
        try:
            default_decimal = Decimal(str(current)) if current not in (None, "") else Decimal("0")
        except InvalidOperation:
            default_decimal = Decimal("0")
        value = st.number_input(
            label,
            value=float(default_decimal),
            step=0.01,
            format="%.4f",
            key=key,
        )
        return float(value)

    if dtype == "date":
        return st.date_input(label, value=parse_date(current), key=key).isoformat()

    if dtype == "timestamp":
        text = st.text_input(
            label,
            value=parse_datetime_text(current),
            placeholder="2026-09-11T15:00:00+09:00",
            key=key,
        )
        return text.strip()

    if column_name in {"preferential_conditions", "source_url"}:
        return st.text_area(label, value=str(current or ""), key=key).strip()

    return st.text_input(label, value=str(current or ""), key=key).strip()


def build_insert_payload(table_name: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name, meta in TABLES[table_name]["columns"].items():
        if meta.get("generated"):
            st.caption(f"{column_label(name)}: 데이터베이스에서 자동 생성됩니다.")
            continue
        if meta.get("default"):
            use_default = st.checkbox(
                f"{column_label(name)}에 데이터베이스 기본값 사용",
                value=True,
                key=f"insert_default_{table_name}_{name}",
            )
            if use_default:
                continue
        if meta.get("nullable"):
            set_null = st.checkbox(
                f"{column_label(name)}을(를) NULL로 저장",
                value=False,
                key=f"insert_null_{table_name}_{name}",
            )
            if set_null:
                payload[name] = None
                continue
        payload[name] = scalar_input(name, meta, key=f"insert_{table_name}_{name}")
    return payload


def build_update_payload(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    pk = TABLES[table_name]["pk"]
    for name, meta in TABLES[table_name]["columns"].items():
        if name == pk:
            continue
        if meta.get("nullable"):
            set_null = st.checkbox(
                f"{column_label(name)}을(를) NULL로 저장",
                value=row.get(name) is None,
                key=f"update_null_{table_name}_{row.get(pk)}_{name}",
            )
            if set_null:
                payload[name] = None
                continue
        payload[name] = scalar_input(
            name,
            meta,
            key=f"update_{table_name}_{row.get(pk)}_{name}",
            current=row.get(name),
        )
    return payload


def fetch_page(
    client: Client,
    table_name: str,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int | None]:
    pk = TABLES[table_name]["pk"]
    start = (page - 1) * page_size
    end = start + page_size - 1
    response = (
        client.table(table_name)
        .select("*", count="exact")
        .order(pk)
        .range(start, end)
        .execute()
    )
    return response.data or [], response.count


def fetch_chart_rows(client: Client, table_name: str, limit: int = CHART_ROW_LIMIT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    batch_size = 1000
    start = 0
    while start < limit:
        end = min(start + batch_size - 1, limit - 1)
        response = client.table(table_name).select("*").range(start, end).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < batch_size:
            break
        start += batch_size
    return rows[:limit]


def fetch_one(client: Client, table_name: str, pk_value: Any) -> dict[str, Any] | None:
    pk = TABLES[table_name]["pk"]
    response = client.table(table_name).select("*").eq(pk, pk_value).limit(1).execute()
    data = response.data or []
    return data[0] if data else None


def format_row_option(table_name: str, row: dict[str, Any]) -> str:
    pk = TABLES[table_name]["pk"]
    summary_fields = [k for k in row.keys() if k != pk][:2]
    summary = " | ".join(f"{column_label(k)}={row.get(k)}" for k in summary_fields)
    return f"{column_label(pk)}={row.get(pk)}" + (f" | {summary}" if summary else "")


def connect_client(url: str, key: str) -> Client:
    if not url or not key:
        raise ValueError("Supabase URL과 API Key를 입력해 주세요.")
    client = create_client(url.strip(), key.strip())
    client.table("branches").select("branch_id").limit(1).execute()
    return client


def korean_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.rename(columns={column: column_label(column) for column in df.columns})


def to_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def render_branches_charts(df: pd.DataFrame) -> None:
    st.subheader("지점 현황 시각화")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**지역별 지점 수**")
        region_counts = df["region"].fillna("미분류").value_counts().rename("지점 수")
        st.bar_chart(region_counts)
    with c2:
        st.markdown("**지역별 지점 구성**")
        region_df = region_counts.reset_index()
        region_df.columns = ["지역", "지점 수"]
        st.dataframe(region_df, use_container_width=True, hide_index=True)


def render_members_charts(df: pd.DataFrame) -> None:
    st.subheader("조합원 현황 시각화")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**지점별 조합원 수**")
        branch_counts = df.groupby("branch_id").size().sort_values(ascending=False).rename("조합원 수")
        branch_counts.index = branch_counts.index.map(lambda x: f"지점 {x}")
        st.bar_chart(branch_counts)
    with c2:
        st.markdown("**성별 조합원 수**")
        gender_counts = df["gender"].fillna("미분류").value_counts().rename("조합원 수")
        st.bar_chart(gender_counts)

    if "join_date" in df.columns:
        join_dates = pd.to_datetime(df["join_date"], errors="coerce")
        monthly = (
            pd.DataFrame({"가입월": join_dates.dt.to_period("M").astype(str)})
            .dropna()
            .value_counts("가입월")
            .sort_index()
            .rename("신규 조합원 수")
        )
        if not monthly.empty:
            st.markdown("**월별 신규 가입 추이**")
            st.line_chart(monthly)


def render_deposit_charts(df: pd.DataFrame) -> None:
    st.subheader("예금 계좌 현황 시각화")
    df = to_numeric(df.copy(), ["balance", "interest_rate"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**계좌 종류별 총 잔액**")
        totals = df.groupby("account_type")["balance"].sum().sort_values(ascending=False)
        totals.index.name = "계좌 종류"
        st.bar_chart(totals)
    with c2:
        st.markdown("**계좌 종류별 평균 금리**")
        rates = df.groupby("account_type")["interest_rate"].mean().sort_values(ascending=False)
        rates.index.name = "계좌 종류"
        st.bar_chart(rates)

    st.markdown("**지점별 예금 총액**")
    branch_totals = df.groupby("branch_id")["balance"].sum().sort_values(ascending=False)
    branch_totals.index = branch_totals.index.map(lambda x: f"지점 {x}")
    st.bar_chart(branch_totals)


def render_loans_charts(df: pd.DataFrame) -> None:
    st.subheader("대출 현황 시각화")
    df = to_numeric(df.copy(), ["loan_amount", "interest_rate"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**대출 상태별 총 대출금액**")
        by_status = df.groupby("status")["loan_amount"].sum().sort_values(ascending=False)
        st.bar_chart(by_status)
    with c2:
        st.markdown("**대출 종류별 평균 금리**")
        by_type_rate = df.groupby("loan_type")["interest_rate"].mean().sort_values(ascending=False)
        st.bar_chart(by_type_rate)

    st.markdown("**지점별 대출 총액**")
    by_branch = df.groupby("branch_id")["loan_amount"].sum().sort_values(ascending=False)
    by_branch.index = by_branch.index.map(lambda x: f"지점 {x}")
    st.bar_chart(by_branch)


def render_transactions_charts(df: pd.DataFrame) -> None:
    st.subheader("거래 현황 시각화")
    df = to_numeric(df.copy(), ["amount", "balance_after"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**거래 종류별 총 거래금액**")
        by_type_amount = df.groupby("transaction_type")["amount"].sum().sort_values(ascending=False)
        st.bar_chart(by_type_amount)
    with c2:
        st.markdown("**거래 종류별 거래 건수**")
        by_type_count = df.groupby("transaction_type").size().sort_values(ascending=False).rename("거래 건수")
        st.bar_chart(by_type_count)

    if "transaction_date" in df.columns:
        dates = pd.to_datetime(df["transaction_date"], errors="coerce")
        trend_df = pd.DataFrame({"거래일": dates.dt.date, "거래금액": df["amount"]}).dropna()
        daily = trend_df.groupby("거래일")["거래금액"].sum().sort_index()
        if not daily.empty:
            st.markdown("**일별 거래금액 추이**")
            st.line_chart(daily)


def render_rate_charts(df: pd.DataFrame) -> None:
    st.subheader("금융기관 예금금리 시각화")
    df = to_numeric(df.copy(), ["base_rate", "maximum_preferential_rate"])
    rate_df = (
        df[["financial_institution_name", "base_rate", "maximum_preferential_rate"]]
        .dropna(subset=["financial_institution_name"])
        .set_index("financial_institution_name")
        .rename(columns={
            "base_rate": "기본금리(%)",
            "maximum_preferential_rate": "최고우대금리(%)",
        })
    )
    st.markdown("**금융기관별 기본금리 및 최고우대금리 비교**")
    st.bar_chart(rate_df)

    st.markdown("**권역별 평균 최고우대금리**")
    by_region = df.groupby("region_category")["maximum_preferential_rate"].mean().sort_values(ascending=False)
    st.bar_chart(by_region)


def render_table_charts(table_name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("그래프로 표시할 데이터가 없습니다.")
        return

    df = pd.DataFrame(rows)
    if table_name == "branches":
        render_branches_charts(df)
    elif table_name == "members":
        render_members_charts(df)
    elif table_name == "deposit_accounts":
        render_deposit_charts(df)
    elif table_name == "loans":
        render_loans_charts(df)
    elif table_name == "transactions":
        render_transactions_charts(df)
    elif table_name == "financial_institution_deposit_rates":
        render_rate_charts(df)


st.title("Supabase 데이터 관리 대시보드")
st.caption(f"Streamlit + supabase-py | 스키마 기준일: {SCHEMA_SNAPSHOT}")

with st.sidebar:
    st.header("Supabase 연결")
    default_url = configured_value("SUPABASE_URL") or DEFAULT_SUPABASE_URL
    default_key = (
        configured_value("SUPABASE_KEY", "SUPABASE_PUBLISHABLE_KEY")
        or DEFAULT_SUPABASE_PUBLISHABLE_KEY
    )

    supabase_url = st.text_input(
        "Supabase URL",
        value=default_url,
        placeholder="https://프로젝트ID.supabase.co",
    )
    supabase_key = st.text_input(
        "Supabase API Key",
        value=default_key,
        type="password",
        help="운영 환경에서는 st.secrets 또는 환경변수를 권장합니다. Git 저장소에 Key를 직접 올리지 마세요.",
    )

    col_connect, col_clear = st.columns(2)
    if col_connect.button("다시 연결", type="primary", use_container_width=True):
        try:
            st.session_state["supabase_client"] = connect_client(supabase_url, supabase_key)
            st.session_state["connected_url"] = supabase_url
            st.success("Supabase 연결 완료")
        except Exception as exc:
            st.session_state.pop("supabase_client", None)
            st.error(f"연결 실패: {exc}")

    if col_clear.button("연결 해제", use_container_width=True):
        st.session_state.pop("supabase_client", None)
        st.session_state.pop("connected_url", None)
        st.rerun()

    st.divider()
    allow_write = st.checkbox(
        "데이터 추가/수정/삭제 허용",
        value=False,
        help="체크해야 INSERT, UPDATE, DELETE 기능을 사용할 수 있습니다.",
    )
    st.caption("공개 배포 환경에서는 service_role 또는 secret key를 사용자 화면에 노출하지 마세요.")

client = st.session_state.get("supabase_client")

# 기본 URL/Publishable Key가 포함되어 있으므로 최초 실행 시 자동 연결합니다.
if client is None:
    try:
        client = connect_client(supabase_url, supabase_key)
        st.session_state["supabase_client"] = client
        st.session_state["connected_url"] = supabase_url
    except Exception as exc:
        st.error(f"Supabase 자동 연결 실패: {exc}")

rls_off = [table_label(name) for name, cfg in TABLES.items() if not cfg["rls"]]
with st.expander("보안 상태", expanded=True):
    st.warning(
        "현재 확인된 스키마 기준으로 다음 테이블은 RLS가 비활성화되어 있습니다: "
        + ", ".join(rls_off)
        + ". Data API 권한이 열려 있다면 publishable/anon 키로 데이터가 노출되거나 변경될 수 있으므로 운영 전 RLS 정책을 구성하세요."
    )
    st.info(
        "금융기관 예금금리 테이블은 RLS가 활성화되어 있습니다. 실제 조회/수정 가능 여부는 GRANT와 RLS 정책 설정에 따라 달라집니다."
    )

if client is None:
    st.info("기본 Supabase 연결에 실패했습니다. 왼쪽 메뉴에서 URL과 API Key를 확인한 후 다시 연결해 주세요.")
    st.stop()

selected_table = st.selectbox(
    "관리할 테이블",
    list(TABLES.keys()),
    format_func=lambda name: f"{table_label(name)} ({name})",
)
config = TABLES[selected_table]
pk = config["pk"]

summary_a, summary_b, summary_c = st.columns(3)
summary_a.metric("기본키", column_label(pk))
summary_b.metric("컬럼 수", len(config["columns"]))
summary_c.metric("RLS", "활성" if config["rls"] else "비활성")

schema_tab, data_tab, chart_tab, create_tab, update_tab, delete_tab = st.tabs(
    ["테이블 구조", "데이터 조회", "그래프", "데이터 추가", "데이터 수정", "데이터 삭제"]
)

with schema_tab:
    schema_rows = []
    for name, meta in config["columns"].items():
        schema_rows.append(
            {
                "컬럼명": column_label(name),
                "실제 컬럼": name,
                "데이터 타입": meta["type"],
                "NULL 허용": meta.get("nullable", False),
                "기본키": name == pk,
                "자동 생성": meta.get("generated", False),
                "DB 기본값": meta.get("default", False),
            }
        )
    st.dataframe(schema_rows, use_container_width=True, hide_index=True)
    if selected_table == "transactions":
        st.warning(
            "거래 내역을 직접 CRUD하면 계좌 잔액과 거래내역 간 정합성이 깨질 수 있습니다. 운영 환경에서는 입출금 전용 RPC 또는 트랜잭션 로직을 사용하는 것을 권장합니다."
        )

with data_tab:
    page_col, size_col = st.columns([1, 1])
    page = int(page_col.number_input("페이지", min_value=1, value=1, step=1))
    page_size = int(size_col.selectbox("페이지당 행 수", [10, 25, 50, 100], index=1))

    try:
        rows, total_count = fetch_page(client, selected_table, page, page_size)
        search = st.text_input("현재 페이지 검색", placeholder="표시된 값에서 검색어를 입력하세요.")
        displayed_rows = rows
        if search.strip():
            needle = search.casefold().strip()
            displayed_rows = [
                row
                for row in rows
                if needle in json.dumps(row, default=str, ensure_ascii=False).casefold()
            ]
        st.caption(
            f"현재 페이지 {len(rows)}건 조회"
            + (f" / 전체 {total_count}건" if total_count is not None else "")
            + (f" / 검색 결과 {len(displayed_rows)}건" if search.strip() else "")
        )
        st.dataframe(korean_dataframe(displayed_rows), use_container_width=True, hide_index=True)
    except Exception as exc:
        rows = []
        st.error(f"데이터 조회 실패: {exc}")

with chart_tab:
    try:
        chart_rows = fetch_chart_rows(client, selected_table)
        st.caption(f"그래프는 최대 {CHART_ROW_LIMIT:,}건까지 조회하여 계산합니다. 현재 {len(chart_rows):,}건을 사용했습니다.")
        render_table_charts(selected_table, chart_rows)
    except Exception as exc:
        st.error(f"그래프 데이터 조회 실패: {exc}")

with create_tab:
    if not allow_write:
        st.info("왼쪽 메뉴에서 '데이터 추가/수정/삭제 허용'을 체크하면 데이터를 추가할 수 있습니다.")
    else:
        with st.form(f"create_{selected_table}", clear_on_submit=False):
            st.subheader(f"{table_label(selected_table)} 데이터 추가")
            insert_payload = build_insert_payload(selected_table)
            submitted = st.form_submit_button("추가", type="primary")
            if submitted:
                try:
                    response = client.table(selected_table).insert(insert_payload).execute()
                    st.success("데이터가 추가되었습니다.")
                    st.dataframe(korean_dataframe(response.data or []), use_container_width=True, hide_index=True)
                except Exception as exc:
                    st.error(f"데이터 추가 실패: {exc}")

with update_tab:
    if not allow_write:
        st.info("왼쪽 메뉴에서 '데이터 추가/수정/삭제 허용'을 체크하면 데이터를 수정할 수 있습니다.")
    elif not rows:
        st.info("현재 조회 페이지에 수정할 데이터가 없습니다.")
    else:
        row_options = {format_row_option(selected_table, row): row.get(pk) for row in rows}
        selected_label = st.selectbox(
            "수정할 행 선택",
            list(row_options.keys()),
            key=f"update_select_{selected_table}",
        )
        selected_pk = row_options[selected_label]
        try:
            current_row = fetch_one(client, selected_table, selected_pk)
        except Exception as exc:
            current_row = None
            st.error(f"수정 대상 데이터 조회 실패: {exc}")

        if current_row:
            st.caption(f"기본키는 수정할 수 없습니다: {column_label(pk)} = {selected_pk}")
            with st.form(f"update_{selected_table}_{selected_pk}"):
                update_payload = build_update_payload(selected_table, current_row)
                submitted = st.form_submit_button("수정 저장", type="primary")
                if submitted:
                    try:
                        response = (
                            client.table(selected_table)
                            .update(update_payload)
                            .eq(pk, selected_pk)
                            .execute()
                        )
                        st.success("데이터가 수정되었습니다.")
                        st.dataframe(korean_dataframe(response.data or []), use_container_width=True, hide_index=True)
                    except Exception as exc:
                        st.error(f"데이터 수정 실패: {exc}")

with delete_tab:
    if not allow_write:
        st.info("왼쪽 메뉴에서 '데이터 추가/수정/삭제 허용'을 체크하면 데이터를 삭제할 수 있습니다.")
    elif not rows:
        st.info("현재 조회 페이지에 삭제할 데이터가 없습니다.")
    else:
        delete_options = {format_row_option(selected_table, row): row.get(pk) for row in rows}
        delete_label = st.selectbox(
            "삭제할 행 선택",
            list(delete_options.keys()),
            key=f"delete_select_{selected_table}",
        )
        delete_pk = delete_options[delete_label]
        target = next((row for row in rows if row.get(pk) == delete_pk), None)
        if target:
            st.dataframe(korean_dataframe([target]), use_container_width=True, hide_index=True)

        confirm_phrase = f"삭제 {delete_pk}"
        confirm_text = st.text_input(
            f"삭제하려면 '{confirm_phrase}'을(를) 입력하세요.",
            key=f"delete_confirm_{selected_table}_{delete_pk}",
        )
        confirmed = confirm_text.strip() == confirm_phrase
        if st.button(
            "선택 행 삭제",
            type="primary",
            disabled=not confirmed,
            key=f"delete_button_{selected_table}_{delete_pk}",
        ):
            try:
                response = client.table(selected_table).delete().eq(pk, delete_pk).execute()
                st.success("데이터가 삭제되었습니다.")
                if response.data:
                    st.dataframe(korean_dataframe(response.data), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"데이터 삭제 실패: {exc}")
