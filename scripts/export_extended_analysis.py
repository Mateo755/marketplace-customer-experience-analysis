"""
Build order-level mart from raw CSVs (equivalent to mart_order_fact)
and export H5–H12 descriptive aggregates to data/processed/.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_DIR = PROJECT_ROOT / "data" / "processed"


def build_mart_order_fact() -> pd.DataFrame:
    orders = pd.read_csv(RAW_DIR / "olist_orders_dataset.csv", parse_dates=[
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ])
    customers = pd.read_csv(RAW_DIR / "olist_customers_dataset.csv")
    items = pd.read_csv(RAW_DIR / "olist_order_items_dataset.csv")
    reviews = pd.read_csv(RAW_DIR / "olist_order_reviews_dataset.csv")

    item_agg = (
        items.groupby("order_id", as_index=False)
        .agg(
            item_count=("order_item_id", "count"),
            seller_count=("seller_id", "nunique"),
            item_revenue=("price", "sum"),
            freight_revenue=("freight_value", "sum"),
        )
    )
    item_agg["order_gmv"] = item_agg["item_revenue"] + item_agg["freight_revenue"]

    review_agg = reviews.groupby("order_id", as_index=False).agg(
        review_score=("review_score", "mean")
    )

    mart = (
        orders.merge(customers, on="customer_id", how="inner")
        .merge(item_agg, on="order_id", how="left")
        .merge(review_agg, on="order_id", how="left")
    )

    mart["delivery_days"] = (
        mart["order_delivered_customer_date"] - mart["order_purchase_timestamp"]
    ).dt.days
    mart["delivery_delay_days"] = (
        mart["order_delivered_customer_date"] - mart["order_estimated_delivery_date"]
    ).dt.days
    mart["is_late_delivery"] = np.where(
        mart["order_delivered_customer_date"].isna(),
        np.nan,
        (
            mart["order_delivered_customer_date"]
            > mart["order_estimated_delivery_date"]
        ).astype(float),
    )
    mart["is_low_review"] = np.where(
        mart["review_score"].isna(),
        np.nan,
        (mart["review_score"] <= 2).astype(float),
    )
    return mart


def delivered_reviewed(mart: pd.DataFrame) -> pd.DataFrame:
    return mart[
        (mart["order_status"] == "delivered") & mart["review_score"].notna()
    ].copy()


def export_region(df: pd.DataFrame) -> None:
    base = df[df["is_late_delivery"].notna()]
    summary = (
        base.groupby("customer_state", as_index=False)
        .agg(
            orders=("order_id", "count"),
            late_delivery_rate_pct=("is_late_delivery", lambda s: 100 * s.mean()),
            avg_review_score=("review_score", "mean"),
            low_review_rate_pct=("is_low_review", lambda s: 100 * s.mean()),
        )
    )
    summary = summary[summary["orders"] >= 200].sort_values(
        ["low_review_rate_pct", "orders"], ascending=[False, False]
    )
    for col in ["late_delivery_rate_pct", "avg_review_score", "low_review_rate_pct"]:
        summary[col] = summary[col].round(2)
    summary.to_csv(OUT_DIR / "region_review_analysis.csv", index=False)

    states = set(summary["customer_state"])
    stratified = base[base["customer_state"].isin(states)].copy()
    stratified["delivery_status"] = np.where(
        stratified["is_late_delivery"] == 1, "Late", "On time or early"
    )
    strat = (
        stratified.groupby(["customer_state", "delivery_status"], as_index=False)
        .agg(
            orders=("order_id", "count"),
            avg_review_score=("review_score", "mean"),
            low_review_rate_pct=("is_low_review", lambda s: 100 * s.mean()),
        )
    )
    strat["avg_review_score"] = strat["avg_review_score"].round(2)
    strat["low_review_rate_pct"] = strat["low_review_rate_pct"].round(2)
    strat.to_csv(OUT_DIR / "region_late_stratified.csv", index=False)


def export_freight(df: pd.DataFrame) -> None:
    base = df[
        df["item_revenue"].notna()
        & (df["item_revenue"] > 0)
        & df["freight_revenue"].notna()
    ].copy()
    base["freight_ratio"] = base["freight_revenue"] / base["item_revenue"]
    base["freight_ratio_tercile"] = pd.qcut(
        base["freight_ratio"].rank(method="first"),
        q=3,
        labels=[1, 2, 3],
    ).astype(int)
    labels = {
        1: "Low freight ratio",
        2: "Mid freight ratio",
        3: "High freight ratio",
    }
    base["freight_ratio_bucket"] = base["freight_ratio_tercile"].map(labels)

    summary = (
        base.groupby(["freight_ratio_tercile", "freight_ratio_bucket"], as_index=False)
        .agg(
            orders=("order_id", "count"),
            avg_freight_ratio=("freight_ratio", "mean"),
            avg_review_score=("review_score", "mean"),
            low_review_rate_pct=("is_low_review", lambda s: 100 * s.mean()),
        )
        .sort_values("freight_ratio_tercile")
    )
    summary["avg_freight_ratio"] = summary["avg_freight_ratio"].round(3)
    summary["avg_review_score"] = summary["avg_review_score"].round(2)
    summary["low_review_rate_pct"] = summary["low_review_rate_pct"].round(2)
    summary.to_csv(OUT_DIR / "freight_value_review_analysis.csv", index=False)

    late_base = base[base["is_late_delivery"].notna()].copy()
    late_base["delivery_status"] = np.where(
        late_base["is_late_delivery"] == 1, "Late", "On time or early"
    )
    crosstab = (
        late_base.groupby(["freight_ratio_bucket", "delivery_status"], as_index=False)
        .agg(
            orders=("order_id", "count"),
            low_review_rate_pct=("is_low_review", lambda s: 100 * s.mean()),
        )
    )
    crosstab["low_review_rate_pct"] = crosstab["low_review_rate_pct"].round(2)
    crosstab.to_csv(OUT_DIR / "freight_ratio_late_crosstab.csv", index=False)


def export_complexity(df: pd.DataFrame) -> None:
    base = df[df["item_count"].notna() & df["seller_count"].notna()].copy()
    base["item_complexity"] = np.where(base["item_count"] > 1, "Multi-item", "Single-item")
    base["seller_complexity"] = np.where(
        base["seller_count"] > 1, "Multi-seller", "Single-seller"
    )

    summary = (
        base.groupby(["item_complexity", "seller_complexity"], as_index=False)
        .agg(
            orders=("order_id", "count"),
            avg_review_score=("review_score", "mean"),
            low_review_rate_pct=("is_low_review", lambda s: 100 * s.mean()),
            late_delivery_rate_pct=("is_late_delivery", lambda s: 100 * s.mean()),
        )
        .sort_values("low_review_rate_pct", ascending=False)
    )
    for col in ["avg_review_score", "low_review_rate_pct", "late_delivery_rate_pct"]:
        summary[col] = summary[col].round(2)
    summary.to_csv(OUT_DIR / "order_complexity_analysis.csv", index=False)

    late = base[base["is_late_delivery"].notna()].copy()
    late["delivery_status"] = np.where(
        late["is_late_delivery"] == 1, "Late", "On time or early"
    )
    strat = (
        late.groupby(["item_complexity", "delivery_status"], as_index=False)
        .agg(
            orders=("order_id", "count"),
            low_review_rate_pct=("is_low_review", lambda s: 100 * s.mean()),
        )
    )
    strat["low_review_rate_pct"] = strat["low_review_rate_pct"].round(2)
    strat.to_csv(OUT_DIR / "order_complexity_late_stratified.csv", index=False)


def export_category_on_time() -> None:
    orders = pd.read_csv(RAW_DIR / "olist_orders_dataset.csv", parse_dates=[
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ])
    items = pd.read_csv(RAW_DIR / "olist_order_items_dataset.csv")
    reviews = pd.read_csv(RAW_DIR / "olist_order_reviews_dataset.csv")
    products = pd.read_csv(RAW_DIR / "olist_products_dataset.csv")
    translation = pd.read_csv(RAW_DIR / "product_category_name_translation.csv")

    on_time_orders = orders[
        (orders["order_status"] == "delivered")
        & orders["order_delivered_customer_date"].notna()
        & orders["order_estimated_delivery_date"].notna()
        & (
            orders["order_delivered_customer_date"]
            <= orders["order_estimated_delivery_date"]
        )
    ][["order_id"]]

    review_scores = reviews.groupby("order_id", as_index=False)["review_score"].mean()
    products = products.merge(translation, on="product_category_name", how="left")
    products["category"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    ).fillna("unknown")

    item_reviews = (
        items.merge(on_time_orders, on="order_id", how="inner")
        .merge(review_scores, on="order_id", how="inner")
        .merge(products[["product_id", "category"]], on="product_id", how="left")
    )
    item_reviews = item_reviews[item_reviews["review_score"].notna()].copy()
    item_reviews["is_low_review"] = (item_reviews["review_score"] <= 2).astype(int)

    summary = (
        item_reviews.groupby("category", as_index=False)
        .agg(
            items_in_on_time_reviewed_orders=("order_id", "count"),
            avg_review_score=("review_score", "mean"),
            low_review_rate_pct=("is_low_review", lambda s: 100 * s.mean()),
        )
    )
    summary = summary[summary["items_in_on_time_reviewed_orders"] >= 100]
    summary = summary.sort_values(
        ["low_review_rate_pct", "items_in_on_time_reviewed_orders"],
        ascending=[False, False],
    ).head(15)
    summary["avg_review_score"] = summary["avg_review_score"].round(2)
    summary["low_review_rate_pct"] = summary["low_review_rate_pct"].round(2)
    summary.to_csv(OUT_DIR / "category_on_time_risk.csv", index=False)


def export_seller_on_time() -> None:
    orders = pd.read_csv(RAW_DIR / "olist_orders_dataset.csv", parse_dates=[
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ])
    items = pd.read_csv(RAW_DIR / "olist_order_items_dataset.csv")
    reviews = pd.read_csv(RAW_DIR / "olist_order_reviews_dataset.csv")

    review_scores = reviews.groupby("order_id", as_index=False)["review_score"].mean()
    base = (
        items.merge(
            orders[
                (orders["order_status"] == "delivered")
                & orders["order_delivered_customer_date"].notna()
                & orders["order_estimated_delivery_date"].notna()
            ],
            on="order_id",
            how="inner",
        ).merge(review_scores, on="order_id", how="inner")
    )
    base["is_late"] = (
        base["order_delivered_customer_date"] > base["order_estimated_delivery_date"]
    )
    base["is_low"] = base["review_score"] <= 2

    rows = []
    for seller_id, g in base.groupby("seller_id"):
        order_level = g.drop_duplicates("order_id")
        delivered_orders = order_level["order_id"].nunique()
        on_time = order_level[~order_level["is_late"]]
        on_time_orders = on_time["order_id"].nunique()
        if delivered_orders < 50 or on_time_orders < 30:
            continue
        rows.append(
            {
                "seller_id": seller_id,
                "delivered_orders": delivered_orders,
                "on_time_orders": on_time_orders,
                "avg_review_score": round(order_level["review_score"].mean(), 2),
                "low_review_rate_pct": round(100 * order_level["is_low"].mean(), 2),
                "late_delivery_rate_pct": round(100 * order_level["is_late"].mean(), 2),
                "on_time_low_review_rate_pct": round(100 * on_time["is_low"].mean(), 2),
            }
        )

    summary = pd.DataFrame(rows).sort_values(
        ["on_time_low_review_rate_pct", "late_delivery_rate_pct"],
        ascending=[False, False],
    ).head(20)
    summary.to_csv(OUT_DIR / "seller_on_time_risk.csv", index=False)


def export_retention(mart: pd.DataFrame) -> None:
    delivered = mart[mart["order_status"] == "delivered"].copy()
    delivered = delivered.sort_values(["customer_unique_id", "order_purchase_timestamp"])
    delivered["order_number"] = (
        delivered.groupby("customer_unique_id").cumcount() + 1
    )
    delivered["next_order_id"] = delivered.groupby("customer_unique_id")["order_id"].shift(
        -1
    )
    delivered["next_order_purchase_timestamp"] = delivered.groupby("customer_unique_id")[
        "order_purchase_timestamp"
    ].shift(-1)

    first = delivered[
        (delivered["order_number"] == 1)
        & delivered["review_score"].notna()
        & (delivered["order_purchase_timestamp"] < "2018-07-01")
    ].copy()
    first["days_to_next_order"] = (
        first["next_order_purchase_timestamp"] - first["order_purchase_timestamp"]
    ).dt.days
    first["first_order_review_group"] = pd.cut(
        first["review_score"],
        bins=[-np.inf, 2, 3, np.inf],
        labels=["Low review (1-2)", "Neutral review (3)", "High review (4-5)"],
    )

    summary = (
        first.groupby("first_order_review_group", observed=False)
        .agg(
            customers=("customer_unique_id", "count"),
            customers_with_next_order=("next_order_id", lambda s: s.notna().sum()),
            avg_days_to_next_order_among_repeaters=(
                "days_to_next_order",
                "mean",
            ),
        )
        .reset_index()
    )
    summary["repeat_purchase_rate_pct"] = (
        100 * summary["customers_with_next_order"] / summary["customers"]
    ).round(2)
    summary["avg_days_to_next_order_among_repeaters"] = summary[
        "avg_days_to_next_order_among_repeaters"
    ].round(1)
    summary.to_csv(OUT_DIR / "retention_timing_analysis.csv", index=False)

    first_late = first[first["is_late_delivery"].notna()].copy()
    first_late["first_order_delivery_status"] = np.where(
        first_late["is_late_delivery"] == 1, "Late", "On time or early"
    )
    context = (
        first_late.groupby(
            ["first_order_review_group", "first_order_delivery_status"],
            observed=False,
        )
        .agg(
            customers=("customer_unique_id", "count"),
            customers_with_next_order=("next_order_id", lambda s: s.notna().sum()),
        )
        .reset_index()
    )
    context["repeat_purchase_rate_pct"] = (
        100 * context["customers_with_next_order"] / context["customers"]
    ).round(2)
    context.to_csv(OUT_DIR / "retention_late_context.csv", index=False)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mart = build_mart_order_fact()
    df = delivered_reviewed(mart)

    export_region(df)
    export_freight(df)
    export_complexity(df)
    export_category_on_time()
    export_seller_on_time()
    export_retention(mart)

    print("Exported extended analysis CSVs to", OUT_DIR)


if __name__ == "__main__":
    main()
