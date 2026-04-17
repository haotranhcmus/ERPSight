import pandas as pd
from datetime import datetime
from typing import List, Tuple, Any


def _to_df(maybe_list: Any) -> pd.DataFrame:
    if isinstance(maybe_list, pd.DataFrame):
        return maybe_list.copy()
    if maybe_list is None:
        return pd.DataFrame()

    rows = []
    for item in maybe_list:
        if hasattr(item, "dict"):
            rows.append(item.dict())
        else:
            rows.append(dict(item))

    return pd.DataFrame(rows)


def preprocess_inventories(inventories: List[Any]) -> pd.DataFrame:
    df = _to_df(inventories)
    if df.empty:
        return df

    if "qty_on_hand" in df.columns and "available_qty" not in df.columns:
        df["available_qty"] = df["qty_on_hand"] - df.get("reserved_quantity", 0)

    cols = [c for c in ["product_id", "available_qty", "reserved_quantity"] if c in df.columns]
    return df[cols]


def preprocess_orders(orders: List[Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    orders_df = _to_df(orders)

    rows = []
    for o in orders:
        odict = o.dict() if hasattr(o, "dict") else dict(o)

        order_date = odict.get("date_order") or odict.get("date")
        if isinstance(order_date, str):
            try:
                order_date = datetime.fromisoformat(order_date)
            except Exception:
                order_date = pd.NaT

        lines = odict.get("lines") or []

        for l in lines:
            ldict = l.dict() if hasattr(l, "dict") else dict(l)

            rows.append({
                "order_id": odict.get("order_id") or odict.get("id"),
                "partner_id": odict.get("partner_id"),
                "date": order_date,
                "product_id": ldict.get("product_id"),
                "price_unit": ldict.get("price_unit") or 0,
                "product_qty": ldict.get("quantity") or ldict.get("product_uom_qty") or 0,
                "price_subtotal": ldict.get("price_subtotal") or 0,
            })

    order_lines_df = pd.DataFrame(rows)
    return orders_df, order_lines_df


def preprocess_purchase_lines(purchase_lines: List[Any]) -> pd.DataFrame:
    return _to_df(purchase_lines)


def preprocess_tickets(tickets: List[Any]) -> pd.DataFrame:
    df = _to_df(tickets)

    if "create_date" in df.columns:
        df["create_date"] = pd.to_datetime(df["create_date"], errors="coerce")

    return df


# =========================
# FEATURE ENGINEERING
# =========================

def build_product_features(
    inventory_df: pd.DataFrame,
    order_lines: pd.DataFrame,
    purchase_lines: pd.DataFrame
) -> pd.DataFrame:

    if order_lines.empty:
        return pd.DataFrame()

    order_lines = order_lines.copy()
    order_lines["revenue"] = order_lines["price_unit"] * order_lines["product_qty"]

    order_agg = (
        order_lines.groupby(["date", "product_id"])
        .agg({
            "product_qty": "sum",
            "revenue": "sum"
        })
        .rename(columns={
            "product_qty": "sold_qty",
            "revenue": "daily_revenue"
        })
        .reset_index()
    )

    # Purchase cost
    purchase_df = purchase_lines.copy()
    if not purchase_df.empty:

        purchase_df["price_unit"] = purchase_df.get("price_unit", 0)
        purchase_df["product_qty"] = purchase_df.get("product_qty", 0)

        purchase_df["cost"] = purchase_df["price_unit"] * purchase_df["product_qty"]

        purchase_agg = purchase_df.groupby("product_id").agg({
            "product_qty": "sum",
            "cost": "sum"
        }).reset_index()

        purchase_agg["avg_cost"] = purchase_agg["cost"] / (purchase_agg["product_qty"] + 1e-6)

        purchase_agg = purchase_agg[["product_id", "avg_cost"]]

    else:
        purchase_agg = pd.DataFrame(columns=["product_id", "avg_cost"])

    df = order_agg.merge(purchase_agg, on="product_id", how="left")

    if not inventory_df.empty:
        df = df.merge(
            inventory_df,
            on="product_id",
            how="left"
        )

    df.fillna(0, inplace=True)
    df = df.sort_values(["product_id", "date"])

    # Margin
    df["estimated_cost"] = df["sold_qty"] * df.get("avg_cost", 0)
    df["margin"] = df["daily_revenue"] - df["estimated_cost"]
    df["margin_ratio"] = df["margin"] / (df["daily_revenue"] + 1e-6)

    # Multi-window
    df["orders_7d_avg"] = df.groupby("product_id")["sold_qty"].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )

    df["orders_30d_avg"] = df.groupby("product_id")["sold_qty"].transform(
        lambda x: x.rolling(30, min_periods=1).mean()
    )

    df["orders_3d_avg"] = df.groupby("product_id")["sold_qty"].transform(
        lambda x: x.rolling(3, min_periods=1).mean()
    )

    df["order_growth_short"] = (
        (df["orders_3d_avg"] - df["orders_7d_avg"]) /
        (df["orders_7d_avg"] + 1e-6)
    )

    df["order_vs_baseline"] = (
        df["orders_7d_avg"] /
        (df["orders_30d_avg"] + 1e-6)
    )

    df.fillna(0, inplace=True)

    return df


def build_customer_features(
    orders_df: pd.DataFrame,
    tickets_df: pd.DataFrame
) -> pd.DataFrame:

    if orders_df.empty:
        return pd.DataFrame()

    orders = orders_df.copy()

    if "date" in orders.columns:
        orders["date"] = pd.to_datetime(orders["date"], errors="coerce")

    orders = orders.sort_values(["partner_id", "date"])

    orders["prev_order"] = orders.groupby("partner_id")["date"].shift(1)
    orders["gap"] = (orders["date"] - orders["prev_order"]).dt.days

    customer = orders.groupby("partner_id").agg({
        "date": "max",
        "gap": "mean"
    }).rename(columns={
        "date": "last_order_date",
        "gap": "avg_gap"
    })

    ticket_info = pd.DataFrame()

    if tickets_df is not None and not tickets_df.empty and "partner_id" in tickets_df.columns:
        tdf = tickets_df.copy()

        if "create_date" in tdf.columns:
            tdf["create_date"] = pd.to_datetime(tdf["create_date"], errors="coerce")

        ticket_info = tdf.groupby("partner_id").agg({
            "create_date": "max"
        }).rename(columns={
            "create_date": "last_ticket_date"
        })

    df = customer.merge(ticket_info, on="partner_id", how="left")

    return df.reset_index()
