import pandas as pd
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta

from .featurizer import *


class ERPAnomalyDetector:

    def __init__(self, window_days=30, contamination=0.05):
        self.window_days = window_days
        self.contamination = contamination

        self.detectors = [
            self.rule_layer,
            self.stat_layer,
            self.ml_layer
        ]

    # =========================
    def make_anomaly(self, row, type_, severity, extra=None):
        return {
            "entity_id": row.entity_id,
            "entity_type": row.entity_type,
            "type": type_,
            "severity": severity,
            "extra": extra or {}
        }

    # =========================
    # RULE LAYER (BUSINESS SCENARIOS)
    # =========================
    def rule_layer(self, row):
        anomalies = []

        # -------------------------
        # SCENARIO 1: SALE SPIKES → MISSED RESTOCK
        # -------------------------
        if row.entity_type == "product":
            if (
                getattr(row, "order_growth_short", 0) > 0.3 and
                getattr(row, "order_vs_baseline", 0) > 1.5 and
                getattr(row, "available_qty", 999) < 10
            ):
                anomalies.append(self.make_anomaly(
                    row,
                    "missed_restock",
                    "high",
                    {
                        "growth": row.order_growth_short,
                        "stock": row.available_qty
                    }
                ))

        # -------------------------
        # SCENARIO 2: SELLING AT LOSS
        # -------------------------
        if row.entity_type == "product":
            if getattr(row, "margin", 0) < 0:
                anomalies.append(self.make_anomaly(
                    row,
                    "negative_margin",
                    "high",
                    {
                        "margin": row.margin,
                        "revenue": getattr(row, "daily_revenue", 0)
                    }
                ))

        # -------------------------
        # SCENARIO 3: POST-TICKET CHURN
        # -------------------------
        if row.entity_type == "customer":

            if hasattr(row, "last_ticket_date") and pd.notna(row.last_ticket_date):

                expected = row.last_order_date + timedelta(days=row.avg_gap or 0)

                if datetime.now() > expected + timedelta(days=3):
                    anomalies.append(self.make_anomaly(
                        row,
                        "post_ticket_churn",
                        "high",
                        {
                            "last_order": str(row.last_order_date),
                            "expected": str(expected)
                        }
                    ))

        return anomalies

    # =========================
    # STATISTICAL LAYER
    # =========================
    def stat_layer(self, row):
        anomalies = []

        if hasattr(row, "zscore"):

            if row.zscore > 3:
                anomalies.append(self.make_anomaly(
                    row,
                    "spike",
                    "medium",
                    {"zscore": row.zscore}
                ))

            elif row.zscore < -3:
                anomalies.append(self.make_anomaly(
                    row,
                    "drop",
                    "medium",
                    {"zscore": row.zscore}
                ))

        return anomalies

    # =========================
    # ML LAYER
    # =========================
    def apply_iforest(self, df):
        if df.empty:
            return df

        model = IsolationForest(contamination=self.contamination)

        features = df[["value", "mean_7"]].fillna(0)
        df["iforest"] = model.fit_predict(features)

        return df

    def ml_layer(self, row):
        if hasattr(row, "iforest") and row.iforest == -1:
            return [self.make_anomaly(
                row,
                "ml_anomaly",
                "low"
            )]
        return []

    # =========================
    # MAIN PIPELINE
    # =========================
    def run(self, inventory, orders, purchase_lines, tickets):

        # -------------------------
        # PREPROCESS
        # -------------------------
        inventory_df = preprocess_inventories(inventory)
        orders_df, order_lines_df = preprocess_orders(orders)
        purchase_lines_df = preprocess_purchase_lines(purchase_lines)
        tickets_df = preprocess_tickets(tickets)

        # -------------------------
        # TIME FILTER
        # -------------------------
        cutoff = datetime.now() - timedelta(days=self.window_days)
        order_lines_df = order_lines_df[order_lines_df["date"] >= cutoff]

        # -------------------------
        # FEATURES
        # -------------------------
        product_df = build_product_features(
            inventory_df, order_lines_df, purchase_lines_df
        )

        customer_df = build_customer_features(orders_df)

        if not tickets_df.empty:
            ticket_info = tickets_df.groupby("partner_id")["create_date"].max().reset_index()
            ticket_info.columns = ["entity_id", "last_ticket_date"]

            customer_df = customer_df.merge(
                ticket_info,
                on="entity_id",
                how="left"
            )

        # -------------------------
        # MERGE ALL ENTITIES
        # -------------------------
        all_df = pd.concat([product_df, customer_df], ignore_index=True)

        # -------------------------
        # ML
        # -------------------------
        all_df = self.apply_iforest(all_df)

        # -------------------------
        # DETECTION
        # -------------------------
        anomalies = []

        for row in all_df.itertuples():
            for detector in self.detectors:
                anomalies.extend(detector(row))

        return anomalies
