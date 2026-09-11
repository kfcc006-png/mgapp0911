import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="Supabase CRUD Dashboard",
    page_icon=":material/database:",
    layout="wide",
)

SCHEMA_SNAPSHOT = "2026-09-11"

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

    if dtype == "integer":
        default = int(current) if current not in (None, "") else 0
        return int(st.number_input(column_name, value=default, step=1, key=key))

    if dtype == "numeric":
        try:
            default_decimal = Decimal(str(current)) if current not in (None, "") else Decimal("0")
        except InvalidOperation:
            default_decimal = Decimal("0")
        value = st.number_input(
            column_name,
            value=float(default_decimal),
            step=0.01,
            format="%.4f",
            key=key,
        )
        return float(value)

    if dtype == "date":
        return st.date_input(column_name, value=parse_date(current), key=key).isoformat()

    if dtype == "timestamp":
        text = st.text_input(
            column_name,
            value=parse_datetime_text(current),
            placeholder="2026-09-11T15:00:00+09:00",
            key=key,
        )
        return text.strip()

    if column_name in {"preferential_conditions", "source_url"}:
        return st.text_area(column_name, value=str(current or ""), key=key).strip()

    return st.text_input(column_name, value=str(current or ""), key=key).strip()


def build_insert_payload(table_name: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name, meta in TABLES[table_name]["columns"].items():
        if meta.get("generated"):
            st.caption(f"{name}: generated by database")
            continue
        if meta.get("default"):
            use_default = st.checkbox(
                f"Use database default for {name}",
                value=True,
                key=f"insert_default_{table_name}_{name}",
            )
            if use_default:
                continue
        if meta.get("nullable"):
            set_null = st.checkbox(
                f"Set {name} to NULL",
                value=False,
                key=f"insert_null_{table_name}_{name}",
            )
            if set_null:
                payload[name] = None
                continue
        payload[name] = scalar_input(
            name,
            meta,
            key=f"insert_{table_name}_{name}",
        )
    return payload


def build_update_payload(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    pk = TABLES[table_name]["pk"]
    for name, meta in TABLES[table_name]["columns"].items():
        if name == pk:
            continue
        if meta.get("nullable"):
            set_null = st.checkbox(
                f"Set {name} to NULL",
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


def fetch_one(client: Client, table_name: str, pk_value: Any) -> dict[str, Any] | None:
    pk = TABLES[table_name]["pk"]
    response = client.table(table_name).select("*").eq(pk, pk_value).limit(1).execute()
    data = response.data or []
    return data[0] if data else None


def format_row_option(table_name: str, row: dict[str, Any]) -> str:
    pk = TABLES[table_name]["pk"]
    summary_fields = [k for k in row.keys() if k != pk][:2]
    summary = " | ".join(f"{k}={row.get(k)}" for k in summary_fields)
    return f"{pk}={row.get(pk)}" + (f" | {summary}" if summary else "")


def connect_client(url: str, key: str) -> Client:
    if not url or not key:
        raise ValueError("Supabase URL and key are required.")
    client = create_client(url.strip(), key.strip())
    client.table("branches").select("branch_id").limit(1).execute()
    return client


st.title("Supabase CRUD Dashboard")
st.caption(
    "Streamlit + supabase-py | Schema snapshot: " + SCHEMA_SNAPSHOT
)

with st.sidebar:
    st.header("Connection")
    default_url = configured_value("SUPABASE_URL")
    default_key = configured_value("SUPABASE_KEY", "SUPABASE_PUBLISHABLE_KEY")

    supabase_url = st.text_input("SUPABASE_URL", value=default_url)
    supabase_key = st.text_input(
        "SUPABASE_KEY",
        value=default_key,
        type="password",
        help="Prefer st.secrets or environment variables. Do not commit keys to Git.",
    )

    col_connect, col_clear = st.columns(2)
    if col_connect.button("Connect", type="primary", use_container_width=True):
        try:
            st.session_state["supabase_client"] = connect_client(supabase_url, supabase_key)
            st.session_state["connected_url"] = supabase_url
            st.success("Connected")
        except Exception as exc:
            st.session_state.pop("supabase_client", None)
            st.error(f"Connection failed: {exc}")

    if col_clear.button("Clear", use_container_width=True):
        st.session_state.pop("supabase_client", None)
        st.session_state.pop("connected_url", None)
        st.rerun()

    st.divider()
    allow_write = st.checkbox(
        "Enable write actions",
        value=False,
        help="Required before INSERT, UPDATE, or DELETE controls are enabled.",
    )
    st.caption("For a public/shared deployment, never expose a service-role or secret key.")

client = st.session_state.get("supabase_client")

rls_off = [name for name, cfg in TABLES.items() if not cfg["rls"]]
with st.expander("Security status", expanded=True):
    st.warning(
        "RLS is disabled on this schema snapshot for: " + ", ".join(rls_off) + ". "
        "With Data API grants, a publishable/anon client can potentially read or modify rows. "
        "Enable RLS and add policies that match your authorization model before production use."
    )
    st.info(
        "The deposit-rate table has RLS enabled. Access to it depends on its grants and RLS policies. "
        "Newer Supabase projects may also require explicit Data API grants for tables."
    )

if client is None:
    st.info("Enter your Supabase URL and key in the sidebar, then click Connect.")
    st.stop()

selected_table = st.selectbox("Table", list(TABLES.keys()))
config = TABLES[selected_table]
pk = config["pk"]

summary_a, summary_b, summary_c = st.columns(3)
summary_a.metric("Primary key", pk)
summary_b.metric("Columns", len(config["columns"]))
summary_c.metric("RLS", "ON" if config["rls"] else "OFF")

schema_tab, data_tab, create_tab, update_tab, delete_tab = st.tabs(
    ["Schema", "Data", "Create", "Update", "Delete"]
)

with schema_tab:
    schema_rows = []
    for name, meta in config["columns"].items():
        schema_rows.append(
            {
                "column": name,
                "type": meta["type"],
                "nullable": meta.get("nullable", False),
                "primary_key": name == pk,
                "generated": meta.get("generated", False),
                "database_default": meta.get("default", False),
            }
        )
    st.dataframe(schema_rows, use_container_width=True, hide_index=True)
    if selected_table == "transactions":
        st.warning(
            "Raw CRUD on transaction rows may break accounting consistency if balances are maintained "
            "by application logic. Prefer a controlled transaction/RPC workflow for production money movement."
        )

with data_tab:
    page_col, size_col = st.columns([1, 1])
    page = int(page_col.number_input("Page", min_value=1, value=1, step=1))
    page_size = int(size_col.selectbox("Rows per page", [10, 25, 50, 100], index=1))

    try:
        rows, total_count = fetch_page(client, selected_table, page, page_size)
        search = st.text_input("Search current page", placeholder="Search any displayed value...")
        displayed_rows = rows
        if search.strip():
            needle = search.casefold().strip()
            displayed_rows = [
                row
                for row in rows
                if needle in json.dumps(row, default=str, ensure_ascii=False).casefold()
            ]
        st.caption(
            f"Loaded {len(rows)} rows"
            + (f" / total {total_count}" if total_count is not None else "")
            + (f" | displayed {len(displayed_rows)}" if search.strip() else "")
        )
        st.dataframe(displayed_rows, use_container_width=True, hide_index=True)
    except Exception as exc:
        rows = []
        st.error(f"Read failed: {exc}")

with create_tab:
    if not allow_write:
        st.info("Enable 'Enable write actions' in the sidebar to create rows.")
    else:
        with st.form(f"create_{selected_table}", clear_on_submit=False):
            st.subheader(f"Create row in {selected_table}")
            insert_payload = build_insert_payload(selected_table)
            submitted = st.form_submit_button("Insert", type="primary")
            if submitted:
                try:
                    response = client.table(selected_table).insert(insert_payload).execute()
                    st.success("Insert completed.")
                    st.json(response.data)
                except Exception as exc:
                    st.error(f"Insert failed: {exc}")

with update_tab:
    if not allow_write:
        st.info("Enable 'Enable write actions' in the sidebar to update rows.")
    elif not rows:
        st.info("No rows are available on the current Data page.")
    else:
        row_options = {format_row_option(selected_table, row): row.get(pk) for row in rows}
        selected_label = st.selectbox("Row to update", list(row_options.keys()), key=f"update_select_{selected_table}")
        selected_pk = row_options[selected_label]
        try:
            current_row = fetch_one(client, selected_table, selected_pk)
        except Exception as exc:
            current_row = None
            st.error(f"Could not load row: {exc}")

        if current_row:
            st.caption(f"Primary key is locked: {pk}={selected_pk}")
            with st.form(f"update_{selected_table}_{selected_pk}"):
                update_payload = build_update_payload(selected_table, current_row)
                submitted = st.form_submit_button("Update", type="primary")
                if submitted:
                    try:
                        response = (
                            client.table(selected_table)
                            .update(update_payload)
                            .eq(pk, selected_pk)
                            .execute()
                        )
                        st.success("Update completed.")
                        st.json(response.data)
                    except Exception as exc:
                        st.error(f"Update failed: {exc}")

with delete_tab:
    if not allow_write:
        st.info("Enable 'Enable write actions' in the sidebar to delete rows.")
    elif not rows:
        st.info("No rows are available on the current Data page.")
    else:
        delete_options = {format_row_option(selected_table, row): row.get(pk) for row in rows}
        delete_label = st.selectbox("Row to delete", list(delete_options.keys()), key=f"delete_select_{selected_table}")
        delete_pk = delete_options[delete_label]
        target = next((row for row in rows if row.get(pk) == delete_pk), None)
        st.json(target or {})
        confirm_text = st.text_input(
            f"Type DELETE {delete_pk} to confirm",
            key=f"delete_confirm_{selected_table}_{delete_pk}",
        )
        confirmed = confirm_text.strip() == f"DELETE {delete_pk}"
        if st.button(
            "Delete row",
            type="primary",
            disabled=not confirmed,
            key=f"delete_button_{selected_table}_{delete_pk}",
        ):
            try:
                response = client.table(selected_table).delete().eq(pk, delete_pk).execute()
                st.success("Delete completed.")
                st.json(response.data)
            except Exception as exc:
                st.error(f"Delete failed: {exc}")
