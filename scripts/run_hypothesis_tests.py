"""
Run formal hypothesis tests (H1, H5–H12) on order-level data built from raw CSVs.
Writes a results summary CSV and key charts used by the notebook / README.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from statsmodels.stats.contingency_tables import StratifiedTable
from statsmodels.stats.multitest import multipletests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.export_extended_analysis import (  # noqa: E402
    RAW_DIR,
    build_mart_order_fact,
    delivered_reviewed,
)

OUT_DIR = PROJECT_ROOT / "outputs"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ALPHA = 0.05


def cramers_v(table: np.ndarray) -> float:
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    n = table.sum()
    r, k = table.shape
    return float(np.sqrt(chi2 / (n * (min(r, k) - 1))))


def cochran_armitage(contingency: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Two-sided Cochran-Armitage trend test for 2 x k table (rows: success/fail)."""
    # contingency shape: 2 x k, row 0 = low review counts, row 1 = not low
    n_i = contingency.sum(axis=0).astype(float)
    x_i = contingency[0].astype(float)
    n = n_i.sum()
    p = x_i.sum() / n
    t = scores.astype(float)
    numer = np.sum(x_i * t) - p * np.sum(n_i * t)
    denom = np.sqrt(p * (1 - p) * (np.sum(n_i * t**2) - (np.sum(n_i * t) ** 2) / n))
    z = numer / denom
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    return float(z), float(p_value)


def odds_ratio_2x2(table: np.ndarray) -> float:
    a, b = table[0]
    c, d = table[1]
    return float((a * d) / (b * c)) if b * c > 0 else np.nan


def cliff_delta(x: np.ndarray, y: np.ndarray) -> float:
    """Cliff's delta for two samples (effect size for Mann-Whitney)."""
    # Efficient approx via rank domination
    nx, ny = len(x), len(y)
    more = 0
    for xi in x:
        more += np.sum(xi > y) - np.sum(xi < y)
    return float(more / (nx * ny))


def delay_bucket(days: float) -> str | None:
    if pd.isna(days):
        return None
    if days <= 0:
        return "On time or early"
    if days <= 3:
        return "1-3 days late"
    if days <= 7:
        return "4-7 days late"
    return "8+ days late"


def main() -> None:
    sns.set_theme(style="whitegrid", palette="deep")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    mart = build_mart_order_fact()
    df = delivered_reviewed(mart)
    df_delay = df[df["delivery_delay_days"].notna() & df["is_late_delivery"].notna()].copy()
    df_delay["delay_bucket"] = df_delay["delivery_delay_days"].map(delay_bucket)
    bucket_order = [
        "On time or early",
        "1-3 days late",
        "4-7 days late",
        "8+ days late",
    ]
    results = []

    # ----- H1: delay bucket vs low review -----
    ct1 = pd.crosstab(df_delay["delay_bucket"], df_delay["is_low_review"]).reindex(
        bucket_order
    )
    # columns: 0.0, 1.0 — ensure order [low=1, not_low=0] for CA as row0=success
    table_h1 = np.array(
        [
            ct1[1.0].values,
            ct1[0.0].values,
        ],
        dtype=float,
    )
    chi2, p_chi, _, _ = stats.chi2_contingency(ct1.values)
    z_ca, p_ca = cochran_armitage(table_h1, np.arange(len(bucket_order)))
    v1 = cramers_v(ct1.values)
    results.append(
        {
            "hypothesis": "H1",
            "question": "Delay bucket vs low review",
            "test": "Chi-square + Cochran-Armitage trend",
            "statistic": round(chi2, 3),
            "p_value": p_chi,
            "trend_z": round(z_ca, 3),
            "trend_p_value": p_ca,
            "effect_size": round(v1, 4),
            "effect_label": "Cramer's V",
            "significant_0_05": p_chi < ALPHA and p_ca < ALPHA,
            "note": "Strong monotonic deterioration with lateness",
        }
    )

    # ----- H5: state vs low review -----
    state_counts = df_delay["customer_state"].value_counts()
    states_ok = state_counts[state_counts >= 200].index
    df_state = df_delay[df_delay["customer_state"].isin(states_ok)]
    ct5 = pd.crosstab(df_state["customer_state"], df_state["is_low_review"])
    chi2_5, p5, _, _ = stats.chi2_contingency(ct5.values)
    v5 = cramers_v(ct5.values)
    results.append(
        {
            "hypothesis": "H5",
            "question": "Customer state vs low review",
            "test": "Chi-square independence",
            "statistic": round(chi2_5, 3),
            "p_value": p5,
            "trend_z": np.nan,
            "trend_p_value": np.nan,
            "effect_size": round(v5, 4),
            "effect_label": "Cramer's V",
            "significant_0_05": p5 < ALPHA,
            "note": "Regional differences exist; effect size is small vs delay",
        }
    )

    # ----- H5b: Mantel-Haenszel late vs low, strata = state -----
    tables = []
    for state, g in df_state.groupby("customer_state"):
        ct = pd.crosstab(g["is_late_delivery"], g["is_low_review"])
        # Need full 2x2
        ct = ct.reindex(index=[0.0, 1.0], columns=[0.0, 1.0], fill_value=0)
        if ct.values.sum() > 0 and (ct.values > 0).all():
            tables.append(ct.values)
        elif ct.values.sum() >= 20:
            # allow zeros for StratifiedTable
            tables.append(ct.values + 0.0)
    st = StratifiedTable(tables)
    mh = st.test_null_odds()
    common_or = float(st.oddsratio_pooled)
    results.append(
        {
            "hypothesis": "H5b",
            "question": "Late vs low review within states (MH)",
            "test": "Mantel-Haenszel",
            "statistic": round(float(mh.statistic), 3),
            "p_value": float(mh.pvalue),
            "trend_z": np.nan,
            "trend_p_value": np.nan,
            "effect_size": round(common_or, 3),
            "effect_label": "Common OR (late)",
            "significant_0_05": float(mh.pvalue) < ALPHA,
            "note": "Delay effect persists after stratifying by state",
        }
    )

    # ----- H6/H7: freight ratio terciles -----
    freight = df[
        df["item_revenue"].notna()
        & (df["item_revenue"] > 0)
        & df["freight_revenue"].notna()
    ].copy()
    freight["freight_ratio"] = freight["freight_revenue"] / freight["item_revenue"]
    freight["tercile"] = pd.qcut(
        freight["freight_ratio"].rank(method="first"), 3, labels=[1, 2, 3]
    ).astype(int)
    ct6 = pd.crosstab(freight["tercile"], freight["is_low_review"])
    chi2_6, p6, _, _ = stats.chi2_contingency(ct6.values)
    table_ca6 = np.array([ct6[1.0].values, ct6[0.0].values], dtype=float)
    z6, p_ca6 = cochran_armitage(table_ca6, np.array([1, 2, 3]))
    v6 = cramers_v(ct6.values)
    results.append(
        {
            "hypothesis": "H6/H7",
            "question": "Freight-ratio tercile vs low review",
            "test": "Chi-square + Cochran-Armitage",
            "statistic": round(chi2_6, 3),
            "p_value": p6,
            "trend_z": round(z6, 3),
            "trend_p_value": p_ca6,
            "effect_size": round(v6, 4),
            "effect_label": "Cramer's V",
            "significant_0_05": p6 < ALPHA,
            "note": "Statistically detectable but much smaller than delay effect",
        }
    )

    # ----- H8: multi-item vs low review -----
    comp = df[df["item_count"].notna()].copy()
    comp["multi_item"] = (comp["item_count"] > 1).astype(int)
    ct8 = pd.crosstab(comp["multi_item"], comp["is_low_review"])
    chi2_8, p8, _, _ = stats.chi2_contingency(ct8.values)
    # OR: multi-item (1) vs low (1)
    ct8_or = ct8.reindex(index=[1, 0], columns=[1.0, 0.0])
    or8 = odds_ratio_2x2(ct8_or.values)
    # Mantel-Haenszel stratified by late
    mh_tables = []
    for late_val, g in comp[comp["is_late_delivery"].notna()].groupby("is_late_delivery"):
        ct = pd.crosstab(g["multi_item"], g["is_low_review"])
        ct = ct.reindex(index=[0, 1], columns=[0.0, 1.0], fill_value=0)
        mh_tables.append(ct.values)
    st8 = StratifiedTable(mh_tables)
    mh8 = st8.test_null_odds()
    results.append(
        {
            "hypothesis": "H8",
            "question": "Multi-item vs low review (MH by late)",
            "test": "Chi-square + Mantel-Haenszel",
            "statistic": round(chi2_8, 3),
            "p_value": p8,
            "trend_z": round(float(mh8.statistic), 3),
            "trend_p_value": float(mh8.pvalue),
            "effect_size": round(or8, 3),
            "effect_label": "OR (multi-item)",
            "significant_0_05": p8 < ALPHA and float(mh8.pvalue) < ALPHA,
            "note": "Complexity associated with low reviews even after late strata",
        }
    )

    # ----- H9: category vs low review among ON-TIME only -----
    orders = pd.read_csv(
        RAW_DIR / "olist_orders_dataset.csv",
        parse_dates=[
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    items = pd.read_csv(RAW_DIR / "olist_order_items_dataset.csv")
    reviews = pd.read_csv(RAW_DIR / "olist_order_reviews_dataset.csv")
    products = pd.read_csv(RAW_DIR / "olist_products_dataset.csv")
    translation = pd.read_csv(RAW_DIR / "product_category_name_translation.csv")
    on_time = orders[
        (orders["order_status"] == "delivered")
        & (
            orders["order_delivered_customer_date"]
            <= orders["order_estimated_delivery_date"]
        )
    ][["order_id"]]
    rev = reviews.groupby("order_id", as_index=False)["review_score"].mean()
    products = products.merge(translation, on="product_category_name", how="left")
    products["category"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    ).fillna("unknown")
    item_ot = (
        items.merge(on_time, on="order_id")
        .merge(rev, on="order_id")
        .merge(products[["product_id", "category"]], on="product_id", how="left")
    )
    item_ot = item_ot[item_ot["review_score"].notna()].copy()
    item_ot["is_low_review"] = (item_ot["review_score"] <= 2).astype(int)
    cat_counts = item_ot["category"].value_counts()
    cats = cat_counts[cat_counts >= 100].index
    item_ot_f = item_ot[item_ot["category"].isin(cats)]
    ct9 = pd.crosstab(item_ot_f["category"], item_ot_f["is_low_review"])
    chi2_9, p9, _, _ = stats.chi2_contingency(ct9.values)
    v9 = cramers_v(ct9.values)

    # Pairwise vs overall on-time rate with BH-FDR (predefined volume filter)
    overall_rate = item_ot_f["is_low_review"].mean()
    pvals = []
    cats_list = []
    for cat, g in item_ot_f.groupby("category"):
        # 2x2: category vs rest for low review
        a = int(g["is_low_review"].sum())
        b = int((1 - g["is_low_review"]).sum())
        rest = item_ot_f[item_ot_f["category"] != cat]
        c = int(rest["is_low_review"].sum())
        d = int((1 - rest["is_low_review"]).sum())
        _, p_i, _, _ = stats.chi2_contingency([[a, b], [c, d]])
        pvals.append(p_i)
        cats_list.append(cat)
    reject, p_adj, _, _ = multipletests(pvals, alpha=ALPHA, method="fdr_bh")
    n_sig_cats = int(reject.sum())
    results.append(
        {
            "hypothesis": "H9",
            "question": "Category vs low review (on-time only)",
            "test": "Chi-square (+ BH-FDR pairwise vs rest)",
            "statistic": round(chi2_9, 3),
            "p_value": p9,
            "trend_z": n_sig_cats,
            "trend_p_value": np.nan,
            "effect_size": round(v9, 4),
            "effect_label": "Cramer's V",
            "significant_0_05": p9 < ALPHA,
            "note": (
                f"On-time-only control for logistics; {n_sig_cats} categories "
                f"differ from rest after FDR (overall on-time low-review "
                f"{100*overall_rate:.2f}%)"
            ),
        }
    )

    # ----- H12: seller vs low among on-time, sellers with >=50 delivered & >=30 on-time -----
    seller_items = items.merge(
        orders[
            (orders["order_status"] == "delivered")
            & orders["order_delivered_customer_date"].notna()
            & orders["order_estimated_delivery_date"].notna()
        ],
        on="order_id",
    ).merge(rev, on="order_id")
    seller_items["is_late"] = (
        seller_items["order_delivered_customer_date"]
        > seller_items["order_estimated_delivery_date"]
    )
    seller_items["is_low"] = seller_items["review_score"] <= 2
    # collapse to order-seller: one row per order_id-seller_id
    seller_orders = seller_items.drop_duplicates(["order_id", "seller_id"])
    eligible = []
    for sid, g in seller_orders.groupby("seller_id"):
        n = g["order_id"].nunique()
        n_ot = g.loc[~g["is_late"], "order_id"].nunique()
        if n >= 50 and n_ot >= 30:
            eligible.append(sid)
    so = seller_orders[
        seller_orders["seller_id"].isin(eligible) & (~seller_orders["is_late"])
    ]
    # one review per order (order may have one seller typically here)
    so_ord = so.drop_duplicates("order_id")
    ct12 = pd.crosstab(so_ord["seller_id"], so_ord["is_low"])
    chi2_12, p12, _, _ = stats.chi2_contingency(ct12.values)
    v12 = cramers_v(ct12.values)
    results.append(
        {
            "hypothesis": "H12",
            "question": "Seller vs low review (on-time orders)",
            "test": "Chi-square",
            "statistic": round(chi2_12, 3),
            "p_value": p12,
            "trend_z": np.nan,
            "trend_p_value": np.nan,
            "effect_size": round(v12, 4),
            "effect_label": "Cramer's V",
            "significant_0_05": p12 < ALPHA,
            "note": "Seller heterogeneity remains after restricting to on-time",
        }
    )

    # ----- H10: first review group vs repeat -----
    delivered = mart[mart["order_status"] == "delivered"].copy()
    delivered = delivered.sort_values(["customer_unique_id", "order_purchase_timestamp"])
    delivered["order_number"] = delivered.groupby("customer_unique_id").cumcount() + 1
    delivered["next_order_id"] = delivered.groupby("customer_unique_id")["order_id"].shift(
        -1
    )
    delivered["next_ts"] = delivered.groupby("customer_unique_id")[
        "order_purchase_timestamp"
    ].shift(-1)
    first = delivered[
        (delivered["order_number"] == 1)
        & delivered["review_score"].notna()
        & (delivered["order_purchase_timestamp"] < "2018-07-01")
    ].copy()
    first["review_group"] = pd.cut(
        first["review_score"],
        bins=[-np.inf, 2, 3, np.inf],
        labels=["Low", "Neutral", "High"],
    )
    first["has_repeat"] = first["next_order_id"].notna().astype(int)
    first["days_to_next"] = (first["next_ts"] - first["order_purchase_timestamp"]).dt.days

    ct10 = pd.crosstab(first["review_group"], first["has_repeat"])
    chi2_10, p10, _, _ = stats.chi2_contingency(ct10.values)
    v10 = cramers_v(ct10.values)
    rates = first.groupby("review_group", observed=True)["has_repeat"].mean()
    delta_pp = 100 * (rates["High"] - rates["Low"])
    results.append(
        {
            "hypothesis": "H10",
            "question": "First-review group vs repeat purchase",
            "test": "Chi-square",
            "statistic": round(chi2_10, 3),
            "p_value": p10,
            "trend_z": np.nan,
            "trend_p_value": np.nan,
            "effect_size": round(delta_pp, 3),
            "effect_label": "Delta pp (High - Low)",
            "significant_0_05": p10 < ALPHA,
            "note": (
                f"Effect is small in magnitude (High {100*rates['High']:.2f}% vs "
                f"Low {100*rates['Low']:.2f}%); treat as supplementary signal"
            ),
        }
    )

    # ----- H11: days to repurchase -----
    rep = first[first["has_repeat"] == 1].copy()
    groups = [g["days_to_next"].dropna().values for _, g in rep.groupby("review_group", observed=True)]
    labels_g = list(rep.groupby("review_group", observed=True).groups.keys())
    h_stat, p11 = stats.kruskal(*groups)
    low_days = rep.loc[rep["review_group"] == "Low", "days_to_next"].dropna().values
    high_days = rep.loc[rep["review_group"] == "High", "days_to_next"].dropna().values
    u_stat, p_mw = stats.mannwhitneyu(low_days, high_days, alternative="two-sided")
    cd = cliff_delta(low_days, high_days)
    results.append(
        {
            "hypothesis": "H11",
            "question": "Days to repurchase by first-review group",
            "test": "Kruskal-Wallis (+ Mann-Whitney Low vs High)",
            "statistic": round(float(h_stat), 3),
            "p_value": p11,
            "trend_z": round(float(u_stat), 3),
            "trend_p_value": p_mw,
            "effect_size": round(cd, 4),
            "effect_label": "Cliff's delta (Low vs High)",
            "significant_0_05": p11 < ALPHA,
            "note": (
                "Among repeaters only; interpret cautiously — small practical "
                "retention signal relative to delivery delay"
            ),
        }
    )

    summary = pd.DataFrame(results)
    summary.to_csv(PROCESSED_DIR / "hypothesis_test_summary.csv", index=False)

    # Charts
    fig, ax = plt.subplots(figsize=(9, 5))
    rate_by_bucket = (
        df_delay.groupby("delay_bucket")["is_low_review"].mean().reindex(bucket_order)
        * 100
    )
    sns.barplot(x=rate_by_bucket.index, y=rate_by_bucket.values, ax=ax, color="#2a6f97")
    ax.set_ylabel("Low-review rate (%)")
    ax.set_xlabel("Delivery delay bucket")
    ax.set_title(
        f"H1: Low-review rate by delay (χ² p={p_chi:.2e}, trend p={p_ca:.2e})"
    )
    plt.xticks(rotation=15, ha="right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "h1_delay_significance.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    fr_labels = {1: "Low", 2: "Mid", 3: "High"}
    freight["bucket"] = freight["tercile"].map(fr_labels)
    rates_f = freight.groupby("bucket")["is_low_review"].mean().reindex(["Low", "Mid", "High"]) * 100
    sns.barplot(x=rates_f.index, y=rates_f.values, ax=ax, color="#2a6f97")
    ax.set_ylabel("Low-review rate (%)")
    ax.set_xlabel("Freight-ratio tercile")
    ax.set_title(f"H6/H7: Freight ratio vs low review (χ² p={p6:.3g}, V={v6:.3f})")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "h6_freight_significance.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    rates_r = rates * 100
    sns.barplot(x=list(rates_r.index.astype(str)), y=rates_r.values, ax=ax, color="#2a6f97")
    ax.set_ylabel("Repeat-purchase rate (%)")
    ax.set_xlabel("First-order review group")
    ax.set_title(
        f"H10: Repeat rate by first review (p={p10:.3g}, Δ={delta_pp:.2f} pp)"
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "h10_retention_significance.png", dpi=150)
    plt.close(fig)

    print(summary.to_string(index=False))
    print("\nWrote", PROCESSED_DIR / "hypothesis_test_summary.csv")


if __name__ == "__main__":
    main()
