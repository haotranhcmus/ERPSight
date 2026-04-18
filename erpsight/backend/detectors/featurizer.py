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


# =========================
# PREPROCESS
# =========================

def preprocess_inventories(inventories):
    df = _to_df(inventories)
    if df.empty:
        return df

    if "qty_on_hand" in df.columns and "available_qty" not in df.columns:
        df["available_qty"] = df["qty_on_hand"] - df.get("reserved_quantity", 0)

    return df[["product_id", "available_qty"]]


def preprocess_orders(orders):
    orders_df = _to_df(orders)

    rows = []
    for o in orders:
        odict = o.dict() if hasattr(o, "dict") else dict(o)

        date = odict.get("date_order") or odict.get("date")
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except:
                date = pd.NaT

        for l in odict.get("lines", []):
            ldict = l.dict() if hasattr(l, "dict") else dict(l)

            rows.append({
                "order_id": odict.get("id"),
                "partner_id": odict.get("partner_id"),
                "date": date,
                "product_id": ldict.get("product_id"),
                "price_unit": ldict.get("price_unit") or 0,
                "product_qty": ldict.get("quantity") or 0,
            })

    return orders_df, pd.DataFrame(rows)


def preprocess_purchase_lines(purchase_lines):
    return _to_df(purchase_lines)


def preprocess_tickets(tickets):
    df = _to_df(tickets)
    if "create_date" in df.columns:
        df["create_date"] = pd.to_datetime(df["create_date"], errors="coerce")
    return df


# =========================
# PRODUCT FEATURES
# =========================

def build_product_features(inventory_df, order_lines, purchase_lines):

    if order_lines.empty:
        return pd.DataFrame()

    df = order_lines.copy()
    df["revenue"] = df["price_unit"] * df["product_qty"]

    df = df.groupby(["product_id", "date"]).agg({
        "product_qty": "sum",
        "revenue": "sum"
    }).reset_index()

    df = df.rename(columns={"product_qty": "value"})

    df = df.sort_values(["product_id", "date"])

    # rolling stats
    df["mean_7"] = df.groupby("product_id")["value"].transform(lambda x: x.rolling(7, 1).mean())
    df["std_7"] = df.groupby("product_id")["value"].transform(lambda x: x.rolling(7, 2).std())

    df["zscore"] = (df["value"] - df["mean_7"]) / (df["std_7"] + 1e-6)

    df["entity_id"] = df["product_id"]
    df["entity_type"] = "product"

    return df


# =========================
# CUSTOMER FEATURES
# =========================

def build_customer_features(orders_df):

    if orders_df.empty:
        return pd.DataFrame()

    orders_df["date"] = pd.to_datetime(orders_df["date"], errors="coerce")

    orders_df["flag"] = 1

    df = (
        orders_df.groupby(["partner_id", "date"])
        .agg({"flag": "sum"})
        .reset_index()
    )

    df = df.rename(columns={"flag": "value"})
    df = df.sort_values(["partner_id", "date"])

    df["mean_7"] = df.groupby("partner_id")["value"].transform(lambda x: x.rolling(7, 1).mean())
    df["std_7"] = df.groupby("partner_id")["value"].transform(lambda x: x.rolling(7, 2).std())

    df["zscore"] = (df["value"] - df["mean_7"]) / (df["std_7"] + 1e-6)

    df["entity_id"] = df["partner_id"]
    df["entity_type"] = "customer"

    return df
