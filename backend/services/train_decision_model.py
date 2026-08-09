"""
Trains the company risk-assessment model used by the "Decision" page.

IMPORTANT / HONEST LIMITATION
------------------------------
There is no real historical dataset of "companies that turned out to be
good vs. bad investments" available here. Building a genuinely predictive
supervised model needs labeled outcomes (e.g. did this company's stock/
credit quality actually improve or deteriorate over the following year),
which this project doesn't have.

Instead, this script does what standard credit-risk scorecards (Altman
Z-score, Piotroski F-score) do: encode financial-risk domain knowledge as
a scoring FORMULA, generate a large synthetic dataset of plausible company
feature profiles, label each one using that formula (+ noise, so the model
has to generalize rather than memorize the exact formula), and train a
real scikit-learn classifier on that. You get an actual trained model with
probabilities and feature importances -- but it is fundamentally a
domain-heuristic model, NOT one trained on real-world outcomes. Swap in a
real labeled dataset here the moment one is available (e.g. scraped
historical financials + subsequent stock performance / credit ratings) and
retrain -- the rest of the pipeline (feature extraction, API, UI) doesn't
need to change.

Run: python train_decision_model.py
Produces: decision_model.pkl (scaler + classifier + feature list bundled together)
"""

import numpy as np
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

RANDOM_SEED = 42
N_SAMPLES = 8000

FEATURES = [
    "current_ratio",
    "debt_to_equity",
    "roe_pct",
    "ebitda_margin_pct",
    "pat_margin_pct",
    "interest_coverage_ratio",
    "revenue_yoy_growth_pct",
    "profit_yoy_growth_pct",
    "pe_ratio",
    "pct_from_52w_high",
    "log_market_cap_cr",
]

# Neutral/"healthy average" defaults used when a feature can't be extracted
# for a real company (missing from the source document/NSE quote). Chosen
# to be roughly the median of the synthetic distribution below, so a
# missing feature pulls the prediction toward "typical" rather than
# artificially toward Low or High risk.
DEFAULTS = {
    "current_ratio": 1.4,
    "debt_to_equity": 0.6,
    "roe_pct": 12.0,
    "ebitda_margin_pct": 15.0,
    "pat_margin_pct": 8.0,
    "interest_coverage_ratio": 4.0,
    "revenue_yoy_growth_pct": 8.0,
    "profit_yoy_growth_pct": 8.0,
    "pe_ratio": 22.0,
    "pct_from_52w_high": -15.0,
    "log_market_cap_cr": np.log1p(5000),
}


def _generate_synthetic_dataset(n=N_SAMPLES, seed=RANDOM_SEED):
    rng = np.random.default_rng(seed)

    current_ratio = np.clip(rng.lognormal(mean=np.log(1.4), sigma=0.35, size=n), 0.2, 6)
    debt_to_equity = np.clip(rng.lognormal(mean=np.log(0.6), sigma=0.6, size=n), 0.0, 5)
    roe_pct = np.clip(rng.normal(12, 9, size=n), -30, 45)
    ebitda_margin_pct = np.clip(rng.normal(15, 8, size=n), -10, 45)
    pat_margin_pct = np.clip(rng.normal(8, 6, size=n), -15, 35)
    interest_coverage_ratio = np.clip(rng.lognormal(mean=np.log(4), sigma=0.7, size=n), 0.1, 40)
    revenue_yoy_growth_pct = np.clip(rng.normal(8, 12, size=n), -40, 60)
    profit_yoy_growth_pct = np.clip(rng.normal(8, 20, size=n), -70, 100)
    pe_ratio = np.clip(rng.lognormal(mean=np.log(22), sigma=0.5, size=n), 2, 150)
    pct_from_52w_high = np.clip(rng.normal(-15, 12, size=n), -80, 0)
    market_cap_cr = np.clip(rng.lognormal(mean=np.log(5000), sigma=1.5, size=n), 50, 2_000_000)
    log_market_cap_cr = np.log1p(market_cap_cr)

    X = np.column_stack([
        current_ratio, debt_to_equity, roe_pct, ebitda_margin_pct, pat_margin_pct,
        interest_coverage_ratio, revenue_yoy_growth_pct, profit_yoy_growth_pct,
        pe_ratio, pct_from_52w_high, log_market_cap_cr,
    ])

    # Domain-heuristic risk score: higher is HEALTHIER (lower risk).
    # Weights are directional judgment calls (standard credit-analysis
    # intuition), not fitted to any real data.
    z = (
        0.9 * (current_ratio - 1.0)
        - 1.1 * debt_to_equity
        + 0.05 * roe_pct
        + 0.04 * ebitda_margin_pct
        + 0.05 * pat_margin_pct
        + 0.12 * np.log1p(interest_coverage_ratio)
        + 0.03 * revenue_yoy_growth_pct
        + 0.02 * profit_yoy_growth_pct
        - 0.01 * np.clip(pe_ratio - 15, 0, None)   # extreme high PE = mild extra risk
        + 0.02 * pct_from_52w_high                  # closer to 52w high = healthier signal
        + 0.15 * (log_market_cap_cr - np.log1p(5000))  # larger companies skew lower risk
    )

    # Add noise so the classifier must generalize the *pattern*, not just
    # invert this exact formula -- otherwise it would trivially overfit to
    # the synthetic labeling function.
    z_noisy = z + rng.normal(0, 0.8, size=n)

    # Convert to 3-class labels via terciles of the noisy score.
    low_thresh, high_thresh = np.quantile(z_noisy, [1/3, 2/3])
    y = np.where(z_noisy >= high_thresh, "Low", np.where(z_noisy >= low_thresh, "Medium", "High"))

    return X, y


def train_and_save(out_path="decision_model.pkl"):
    X, y = _generate_synthetic_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    clf = LogisticRegression(max_iter=2000, random_state=RANDOM_SEED)
    clf.fit(X_train_scaled, y_train)

    print("=== Holdout performance (on synthetic data -- see limitation note above) ===")
    print(classification_report(y_test, clf.predict(X_test_scaled)))

    bundle = {
        "scaler": scaler,
        "classifier": clf,
        "features": FEATURES,
        "defaults": DEFAULTS,
        "classes": list(clf.classes_),
    }
    with open(out_path, "wb") as f:
        pickle.dump(bundle, f)
    print(f"Saved model bundle to {out_path}")


if __name__ == "__main__":
    train_and_save()
