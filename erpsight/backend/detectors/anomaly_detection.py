import pandas as pd
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta

from .featurizer import (
    preprocess_inventories,
    preprocess_orders,
    preprocess_purchase_lines,
    preprocess_tickets,
    build_product_features,
    build_customer_features,
)


class ERPAnomalyDetector:

    def __init__(self, window_days=30, contamination=0.05):
        self.window_days = window_days
        self.contamination = contamination
        self.iforest_model = IsolationForest(contamination=self.contamination)

    # =========================
    # UTIL
    # =========================
    def make_anomaly(self, module, entity_id, anomaly_type, severity, extra=None):
        return {
            "module": module,
            "entity_id": entity_id,
            "type": anomaly_type,
            "severity": severity,
            "extra": extra or {}
        }

    # =========================
    # SCENARIOS
    # =========================
    def detect_sale_event(self, row):
        if (
            row.order_growth_short > 0.3 and
            row.order_vs_baseline > 1.5 and
            row.available_qty < 10
        ):
            return self.make_anomaly(
                "inventory",
                row.product_id,
                "missed_restock",
                "high"
            )

    def detect_negative_margin(self, row):
        if row.margin < 0:
            return self.make_anomaly(
                "order",
                row.product_id,
                "negative_margin",
                "high",
                {
                    "margin": row.margin,
                    "revenue": row.daily_revenue
                }
            )

    def detect_churn(self, row):
        if pd.isna(row.last_ticket_date):
            return None

        expected = row.last_order_date + timedelta(days=row.avg_gap or 0)

        if datetime.now() > expected + timedelta(days=3):
            return self.make_anomaly(
                "customer",
                row.partner_id,
                "post_ticket_churn",
                "high"
            )

    # =========================
    # UNSUPERVISED
    # =========================
    def run_iforest(self, df):
        if df.empty:
            return df

        features = df[[
            "available_qty",
            "orders_7d_avg",
            "orders_30d_avg",
            "margin_ratio"
        ]].fillna(0)

        df["iforest_flag"] = self.iforest_model.fit_predict(features)
        return df

    # =========================
    # MAIN PIPELINE
    # =========================
    def run(self, inventory, orders, purchase_lines, tickets):

        anomalies = []

        # -------------------------
        # 1. PREPROCESS
        # -------------------------
        inventory_df = preprocess_inventories(inventory)

        orders_df, order_lines_df = preprocess_orders(orders)

        purchase_lines_df = preprocess_purchase_lines(purchase_lines)

        tickets_df = preprocess_tickets(tickets)

        # -------------------------
        # 2. TIME FILTER
        # -------------------------
        cutoff = datetime.now() - timedelta(days=self.window_days)

        if not order_lines_df.empty:
            order_lines_df = order_lines_df[
                order_lines_df["date"] >= cutoff
            ]

        if not orders_df.empty and "date" in orders_df.columns:
            orders_df["date"] = pd.to_datetime(orders_df["date"], errors="coerce")
            orders_df = orders_df[orders_df["date"] >= cutoff]

        # -------------------------
        # 3. FEATURE ENGINEERING
        # -------------------------
        product_df = build_product_features(
            inventory_df, order_lines_df, purchase_lines_df
        )

        customer_df = build_customer_features(
            orders_df, tickets_df
        )

        # -------------------------
        # 4. UNSUPERVISED
        # -------------------------
        product_df = self.run_iforest(product_df)

        # -------------------------
        # 5. PRODUCT ANOMALIES (vectorized)
        # -------------------------
        if not product_df.empty:

            # Sale event
            sale_mask = (
                (product_df["order_growth_short"] > 0.3) &
                (product_df["order_vs_baseline"] > 1.5) &
                (product_df["available_qty"] < 10)
            )

            for row in product_df[sale_mask].itertuples():
                anomalies.append(self.make_anomaly(
                    "inventory", row.product_id, "missed_restock", "high"
                ))

            # Negative margin
            neg_margin_mask = product_df["margin"] < 0

            for row in product_df[neg_margin_mask].itertuples():
                anomalies.append(self.make_anomaly(
                    "order",
                    row.product_id,
                    "negative_margin",
                    "high",
                    {
                        "margin": row.margin,
                        "revenue": row.daily_revenue
                    }
                ))

            # Isolation Forest
            if "iforest_flag" in product_df.columns:
                for row in product_df[product_df["iforest_flag"] == -1].itertuples():
                    anomalies.append(self.make_anomaly(
                        "global",
                        row.product_id,
                        "unknown_pattern",
                        "low"
                    ))

        # -------------------------
        # 6. CUSTOMER ANOMALIES
        # -------------------------
        if not customer_df.empty:
            for row in customer_df.itertuples():
                res = self.detect_churn(row)
                if res:
                    anomalies.append(res)

        return anomalies
