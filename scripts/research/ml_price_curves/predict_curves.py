"""
ML Price Curve Prediction - Phase 2-5
=======================================
All ML approaches for predicting price curves:
1. Curve Shape Classification (K-Means clustering)
2. Magnitude Prediction (Regression for high%/low%)
3. Timing Prediction (Classify when high/low forms)
4. Dynamic Weighting (Similarity-based curve generation)

With in-sample and out-of-sample validation.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.metrics import accuracy_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import train_test_split
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import joblib

# Config
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

TICKER = "NQ1"

# Data splits
TRAIN_END = "2022-12-31"  # Train on 2008-2022
IN_SAMPLE_END = "2024-06-30"  # In-sample test: 2023 - mid 2024
# Out-of-sample: mid 2024 - present


def load_extracted_data(session_name: str):
    """Load pre-extracted curves and metrics."""
    curves_path = OUTPUT_DIR / f"{TICKER}_{session_name}_curves.npz"
    metrics_path = OUTPUT_DIR / f"{TICKER}_{session_name}_metrics.csv"
    
    curves_data = np.load(curves_path, allow_pickle=True)
    metrics_df = pd.read_csv(metrics_path)
    
    return {
        'highs': curves_data['highs'],
        'lows': curves_data['lows'],
        'dates': curves_data['dates'],
        'metrics': metrics_df
    }


def load_profiler_features():
    """Load full profiler features for ML."""
    file_path = DATA_DIR / f"{TICKER}_profiler.json"
    
    with open(file_path) as f:
        data = json.load(f)
    
    # Group by date and build feature set
    features_by_date = {}
    
    for record in data:
        date = record['date']
        session = record['session']
        
        if date not in features_by_date:
            features_by_date[date] = {}
        
        features_by_date[date][session] = {
            'open': record.get('open', 0),
            'range_high': record.get('range_high', 0),
            'range_low': record.get('range_low', 0),
            'status': record.get('status', ''),
            'broken': record.get('broken', False),
            'prior_close': record.get('prior_close', 0),
        }
    
    return features_by_date


def create_feature_matrix(metrics_df: pd.DataFrame, profiler_features: dict):
    """Build feature matrix from metrics and profiler data."""
    rows = []
    
    for _, row in metrics_df.iterrows():
        date = row['date']
        profiler = profiler_features.get(date, {})
        
        asia = profiler.get('Asia', {})
        london = profiler.get('London', {})
        ny1 = profiler.get('NY1', {})
        
        # Calculate features
        asia_range = asia.get('range_high', 0) - asia.get('range_low', 0)
        london_range = london.get('range_high', 0) - london.get('range_low', 0)
        
        london_expansion = london_range / asia_range if asia_range > 0 else 1
        
        gap = london.get('open', 0) - asia.get('prior_close', london.get('open', 1)) if asia.get('prior_close') else 0
        gap_pct = (gap / asia.get('prior_close', 1) * 100) if asia.get('prior_close') else 0
        
        features = {
            'date': date,
            # From metrics
            'session_open': row['session_open'],
            # Pre-market features
            'asia_broken': row.get('asia_broken', 0),
            'london_broken': row.get('london_broken', 0),
            'asia_long': row.get('asia_long', 0),
            'london_long': row.get('london_long', 0),
            'london_expansion': london_expansion,
            'gap_pct': gap_pct,
            # Targets
            'high_pct': row['high_pct'],
            'low_pct': row['low_pct'],
            'high_time': row['high_time'],
            'low_time': row['low_time'],
            'close_pct': row.get('close_pct', 0),
        }
        
        # Day of week
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            features['day_of_week'] = dt.weekday()
        except:
            features['day_of_week'] = 0
        
        rows.append(features)
    
    return pd.DataFrame(rows)


def cluster_curves(highs: np.ndarray, lows: np.ndarray, n_clusters: int = 5):
    """Cluster curve shapes using K-Means."""
    # Combine high and low curves into single feature vector
    combined = np.hstack([highs, lows])
    
    # Standardize
    scaler = StandardScaler()
    combined_scaled = scaler.fit_transform(combined)
    
    # Cluster
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(combined_scaled)
    
    return labels, kmeans, scaler


def visualize_clusters(highs: np.ndarray, lows: np.ndarray, labels: np.ndarray, session_name: str):
    """Visualize cluster centroids."""
    n_clusters = len(np.unique(labels))
    
    fig = make_subplots(rows=2, cols=3, subplot_titles=[f'Cluster {i}' for i in range(n_clusters)] + [''])
    
    colors = ['#00ff00', '#ff0000', '#0088ff', '#ff8800', '#aa00ff']
    
    for cluster_id in range(min(n_clusters, 6)):
        mask = labels == cluster_id
        count = mask.sum()
        
        cluster_highs = highs[mask]
        cluster_lows = lows[mask]
        
        median_high = np.median(cluster_highs, axis=0)
        median_low = np.median(cluster_lows, axis=0)
        
        row = cluster_id // 3 + 1
        col = cluster_id % 3 + 1
        
        fig.add_trace(
            go.Scatter(x=list(range(len(median_high))), y=median_high,
                       mode='lines', line=dict(color='lime', width=2),
                       name=f'High (n={count})'),
            row=row, col=col
        )
        fig.add_trace(
            go.Scatter(x=list(range(len(median_low))), y=median_low,
                       mode='lines', line=dict(color='red', width=2),
                       name=f'Low (n={count})'),
            row=row, col=col
        )
        fig.add_hline(y=0, line_color='gray', line_dash='dash', row=row, col=col)
    
    fig.update_layout(
        title=f'{session_name} Curve Clusters',
        template='plotly_dark',
        height=600,
        showlegend=False
    )
    
    return fig


def train_shape_classifier(features_df: pd.DataFrame, labels: np.ndarray, train_end: str, in_sample_end: str):
    """Train classifier to predict curve shape from pre-market features."""
    # Add labels to features
    features_df = features_df.copy()
    features_df['cluster'] = labels
    
    # Split by date
    train_mask = features_df['date'] <= train_end
    in_sample_mask = (features_df['date'] > train_end) & (features_df['date'] <= in_sample_end)
    oos_mask = features_df['date'] > in_sample_end
    
    train_df = features_df[train_mask]
    in_sample_df = features_df[in_sample_mask]
    oos_df = features_df[oos_mask]
    
    print(f"\n  Train: {len(train_df)}, In-Sample: {len(in_sample_df)}, OOS: {len(oos_df)}")
    
    # Features
    feature_cols = ['asia_broken', 'london_broken', 'asia_long', 'london_long',
                    'london_expansion', 'gap_pct', 'day_of_week']
    
    X_train = train_df[feature_cols].values
    y_train = train_df['cluster'].values
    
    X_is = in_sample_df[feature_cols].values
    y_is = in_sample_df['cluster'].values
    
    X_oos = oos_df[feature_cols].values
    y_oos = oos_df['cluster'].values
    
    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_is_scaled = scaler.transform(X_is)
    X_oos_scaled = scaler.transform(X_oos)
    
    # Train
    clf = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
    clf.fit(X_train_scaled, y_train)
    
    # Evaluate
    in_sample_acc = accuracy_score(y_is, clf.predict(X_is_scaled))
    oos_acc = accuracy_score(y_oos, clf.predict(X_oos_scaled)) if len(oos_df) > 0 else 0
    
    print(f"  Shape Classifier - In-Sample Acc: {in_sample_acc:.1%}, OOS Acc: {oos_acc:.1%}")
    
    return clf, scaler, feature_cols, {
        'in_sample_acc': in_sample_acc,
        'oos_acc': oos_acc
    }


def train_magnitude_regressor(features_df: pd.DataFrame, target: str, train_end: str, in_sample_end: str):
    """Train regressor to predict session high% or low%."""
    train_mask = features_df['date'] <= train_end
    in_sample_mask = (features_df['date'] > train_end) & (features_df['date'] <= in_sample_end)
    oos_mask = features_df['date'] > in_sample_end
    
    train_df = features_df[train_mask]
    in_sample_df = features_df[in_sample_mask]
    oos_df = features_df[oos_mask]
    
    feature_cols = ['asia_broken', 'london_broken', 'asia_long', 'london_long',
                    'london_expansion', 'gap_pct', 'day_of_week']
    
    X_train = train_df[feature_cols].values
    y_train = train_df[target].values
    
    X_is = in_sample_df[feature_cols].values
    y_is = in_sample_df[target].values
    
    X_oos = oos_df[feature_cols].values
    y_oos = oos_df[target].values
    
    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_is_scaled = scaler.transform(X_is)
    X_oos_scaled = scaler.transform(X_oos)
    
    # Train
    reg = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
    reg.fit(X_train_scaled, y_train)
    
    # Evaluate
    is_pred = reg.predict(X_is_scaled)
    oos_pred = reg.predict(X_oos_scaled)
    
    is_rmse = np.sqrt(mean_squared_error(y_is, is_pred))
    is_mae = mean_absolute_error(y_is, is_pred)
    
    oos_rmse = np.sqrt(mean_squared_error(y_oos, oos_pred)) if len(oos_df) > 0 else 0
    oos_mae = mean_absolute_error(y_oos, oos_pred) if len(oos_df) > 0 else 0
    
    print(f"  {target} Regressor - IS RMSE: {is_rmse:.3f}, OOS RMSE: {oos_rmse:.3f}")
    
    return reg, scaler, {
        'is_rmse': is_rmse, 'is_mae': is_mae,
        'oos_rmse': oos_rmse, 'oos_mae': oos_mae
    }


def train_timing_classifier(features_df: pd.DataFrame, target: str, max_minutes: int,
                            train_end: str, in_sample_end: str):
    """Train classifier to predict timing bucket (early/mid/late)."""
    features_df = features_df.copy()
    
    # Create buckets
    third = max_minutes // 3
    features_df['timing_bucket'] = pd.cut(
        features_df[target],
        bins=[-1, third, 2*third, max_minutes+1],
        labels=['early', 'mid', 'late']
    )
    
    train_mask = features_df['date'] <= train_end
    in_sample_mask = (features_df['date'] > train_end) & (features_df['date'] <= in_sample_end)
    oos_mask = features_df['date'] > in_sample_end
    
    train_df = features_df[train_mask]
    in_sample_df = features_df[in_sample_mask]
    oos_df = features_df[oos_mask]
    
    feature_cols = ['asia_broken', 'london_broken', 'asia_long', 'london_long',
                    'london_expansion', 'gap_pct', 'day_of_week']
    
    X_train = train_df[feature_cols].values
    y_train = train_df['timing_bucket'].astype(str).values
    
    X_is = in_sample_df[feature_cols].values
    y_is = in_sample_df['timing_bucket'].astype(str).values
    
    X_oos = oos_df[feature_cols].values
    y_oos = oos_df['timing_bucket'].astype(str).values
    
    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_is_scaled = scaler.transform(X_is)
    X_oos_scaled = scaler.transform(X_oos)
    
    # Train
    clf = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
    clf.fit(X_train_scaled, y_train)
    
    is_acc = accuracy_score(y_is, clf.predict(X_is_scaled))
    oos_acc = accuracy_score(y_oos, clf.predict(X_oos_scaled)) if len(oos_df) > 0 else 0
    
    print(f"  {target} Timing - IS Acc: {is_acc:.1%}, OOS Acc: {oos_acc:.1%}")
    
    return clf, scaler, {'is_acc': is_acc, 'oos_acc': oos_acc}


def generate_predicted_curve(shape_pred: int, high_pred: float, low_pred: float,
                            cluster_centroids_high: np.ndarray, cluster_centroids_low: np.ndarray):
    """Generate predicted curve from ML outputs."""
    # Get centroid shape
    base_high = cluster_centroids_high[shape_pred]
    base_low = cluster_centroids_low[shape_pred]
    
    # Scale to predicted magnitudes
    base_high_max = base_high.max()
    base_low_min = base_low.min()
    
    if base_high_max != 0:
        scaled_high = base_high * (high_pred / base_high_max)
    else:
        scaled_high = base_high
    
    if base_low_min != 0:
        scaled_low = base_low * (low_pred / base_low_min)
    else:
        scaled_low = base_low
    
    return scaled_high, scaled_low


def visualize_prediction_comparison(actual_highs: np.ndarray, actual_lows: np.ndarray,
                                    pred_highs: np.ndarray, pred_lows: np.ndarray,
                                    dates: list, session_name: str, n_samples: int = 6):
    """Create comparison charts of predicted vs actual curves."""
    fig = make_subplots(rows=2, cols=3, subplot_titles=[f'Day {i+1}' for i in range(n_samples)])
    
    # Take random samples from OOS
    indices = np.random.choice(len(actual_highs), min(n_samples, len(actual_highs)), replace=False)
    
    for i, idx in enumerate(indices):
        row = i // 3 + 1
        col = i % 3 + 1
        
        x = list(range(len(actual_highs[idx])))
        
        # Actual
        fig.add_trace(
            go.Scatter(x=x, y=actual_highs[idx], mode='lines',
                       line=dict(color='lime', width=2), name='Actual High'),
            row=row, col=col
        )
        fig.add_trace(
            go.Scatter(x=x, y=actual_lows[idx], mode='lines',
                       line=dict(color='red', width=2), name='Actual Low'),
            row=row, col=col
        )
        
        # Predicted
        fig.add_trace(
            go.Scatter(x=x, y=pred_highs[idx], mode='lines',
                       line=dict(color='cyan', width=2, dash='dash'), name='Pred High'),
            row=row, col=col
        )
        fig.add_trace(
            go.Scatter(x=x, y=pred_lows[idx], mode='lines',
                       line=dict(color='orange', width=2, dash='dash'), name='Pred Low'),
            row=row, col=col
        )
        
        fig.add_hline(y=0, line_color='gray', line_dash='dot', row=row, col=col)
    
    fig.update_layout(
        title=f'{session_name} - Predicted vs Actual Curves (OOS)',
        template='plotly_dark',
        height=600,
        showlegend=False
    )
    
    return fig


def calculate_curve_distance(actual_highs: np.ndarray, actual_lows: np.ndarray,
                            pred_highs: np.ndarray, pred_lows: np.ndarray):
    """Calculate distance metrics between predicted and actual curves."""
    # RMSE of the full curves
    high_rmse = np.sqrt(np.mean((actual_highs - pred_highs) ** 2))
    low_rmse = np.sqrt(np.mean((actual_lows - pred_lows) ** 2))
    
    # MAE
    high_mae = np.mean(np.abs(actual_highs - pred_highs))
    low_mae = np.mean(np.abs(actual_lows - pred_lows))
    
    return {
        'high_rmse': high_rmse,
        'low_rmse': low_rmse,
        'high_mae': high_mae,
        'low_mae': low_mae,
        'combined_rmse': (high_rmse + low_rmse) / 2
    }


if __name__ == "__main__":
    print("="*70)
    print("ML PRICE CURVE PREDICTION - FULL PIPELINE")
    print("="*70)
    
    profiler_features = load_profiler_features()
    print(f"Loaded profiler features for {len(profiler_features)} days\n")
    
    all_results = {}
    
    for session_name in ['NY_AM', 'NY_PM']:
        print(f"\n{'='*70}")
        print(f"PROCESSING: {session_name}")
        print(f"{'='*70}")
        
        # Load data
        data = load_extracted_data(session_name)
        highs = data['highs']
        lows = data['lows']
        dates = list(data['dates'])
        metrics_df = data['metrics']
        
        print(f"Loaded {len(highs)} curves")
        
        max_minutes = 150 if session_name == 'NY_AM' else 240
        
        # Create feature matrix
        features_df = create_feature_matrix(metrics_df, profiler_features)
        
        # Phase 2: Cluster curves
        print("\n--- Phase 2: Curve Shape Clustering ---")
        n_clusters = 5
        labels, kmeans, cluster_scaler = cluster_curves(highs, lows, n_clusters)
        
        # Calculate cluster centroids
        cluster_centroids_high = []
        cluster_centroids_low = []
        for c in range(n_clusters):
            mask = labels == c
            cluster_centroids_high.append(np.median(highs[mask], axis=0))
            cluster_centroids_low.append(np.median(lows[mask], axis=0))
        cluster_centroids_high = np.array(cluster_centroids_high)
        cluster_centroids_low = np.array(cluster_centroids_low)
        
        # Visualize clusters
        fig_clusters = visualize_clusters(highs, lows, labels, session_name)
        fig_clusters.write_html(OUTPUT_DIR / f'{session_name}_clusters.html')
        print(f"  ✅ Cluster visualization saved")
        
        # Train shape classifier
        print("\n--- Phase 2b: Shape Classifier ---")
        shape_clf, shape_scaler, shape_features, shape_results = train_shape_classifier(
            features_df, labels, TRAIN_END, IN_SAMPLE_END
        )
        
        # Phase 3: Magnitude prediction
        print("\n--- Phase 3: Magnitude Prediction ---")
        high_reg, high_scaler, high_results = train_magnitude_regressor(
            features_df, 'high_pct', TRAIN_END, IN_SAMPLE_END
        )
        low_reg, low_scaler, low_results = train_magnitude_regressor(
            features_df, 'low_pct', TRAIN_END, IN_SAMPLE_END
        )
        
        # Phase 4: Timing prediction
        print("\n--- Phase 4: Timing Prediction ---")
        high_time_clf, high_time_scaler, high_time_results = train_timing_classifier(
            features_df, 'high_time', max_minutes, TRAIN_END, IN_SAMPLE_END
        )
        low_time_clf, low_time_scaler, low_time_results = train_timing_classifier(
            features_df, 'low_time', max_minutes, TRAIN_END, IN_SAMPLE_END
        )
        
        # Phase 5: Generate predictions and compare
        print("\n--- Phase 5: Full Curve Prediction ---")
        
        # Get OOS data
        oos_mask = features_df['date'] > IN_SAMPLE_END
        oos_indices = features_df[oos_mask].index.tolist()
        
        # Map feature indices to curve indices
        date_to_curve_idx = {d: i for i, d in enumerate(dates)}
        oos_curve_indices = [date_to_curve_idx.get(features_df.loc[i, 'date']) for i in oos_indices]
        oos_curve_indices = [i for i in oos_curve_indices if i is not None]
        
        if len(oos_curve_indices) > 0:
            oos_features = features_df[oos_mask]
            X_oos = oos_features[shape_features].values
            X_oos_scaled = shape_scaler.transform(X_oos)
            
            # Predict shape
            shape_preds = shape_clf.predict(X_oos_scaled)
            
            # Predict magnitude
            X_mag_scaled = high_scaler.transform(X_oos)
            high_preds = high_reg.predict(X_mag_scaled)
            low_preds = low_reg.predict(X_mag_scaled)
            
            # Generate predicted curves
            pred_highs = []
            pred_lows = []
            
            for i in range(len(shape_preds)):
                ph, pl = generate_predicted_curve(
                    shape_preds[i], high_preds[i], low_preds[i],
                    cluster_centroids_high, cluster_centroids_low
                )
                pred_highs.append(ph)
                pred_lows.append(pl)
            
            pred_highs = np.array(pred_highs)
            pred_lows = np.array(pred_lows)
            
            # Get actual OOS curves
            actual_highs_oos = highs[oos_curve_indices[:len(pred_highs)]]
            actual_lows_oos = lows[oos_curve_indices[:len(pred_lows)]]
            oos_dates = [dates[i] for i in oos_curve_indices[:len(pred_highs)]]
            
            # Calculate distance
            distance = calculate_curve_distance(actual_highs_oos, actual_lows_oos, pred_highs, pred_lows)
            print(f"\n  Curve Distance (OOS):")
            print(f"    High RMSE: {distance['high_rmse']:.4f}")
            print(f"    Low RMSE: {distance['low_rmse']:.4f}")
            print(f"    Combined RMSE: {distance['combined_rmse']:.4f}")
            
            # Visualize comparison
            fig_compare = visualize_prediction_comparison(
                actual_highs_oos, actual_lows_oos, pred_highs, pred_lows, oos_dates, session_name
            )
            fig_compare.write_html(OUTPUT_DIR / f'{session_name}_prediction_comparison.html')
            print(f"\n  ✅ Prediction comparison saved")
            
            all_results[session_name] = {
                'shape_acc': shape_results,
                'high_magnitude': high_results,
                'low_magnitude': low_results,
                'high_timing': high_time_results,
                'low_timing': low_time_results,
                'curve_distance': distance
            }
        else:
            print("  ⚠️ No OOS data available")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    for session, results in all_results.items():
        print(f"\n{session}:")
        print(f"  Shape Classification OOS Acc: {results['shape_acc']['oos_acc']:.1%}")
        print(f"  High% Magnitude OOS RMSE: {results['high_magnitude']['oos_rmse']:.4f}")
        print(f"  Low% Magnitude OOS RMSE: {results['low_magnitude']['oos_rmse']:.4f}")
        print(f"  High Timing OOS Acc: {results['high_timing']['oos_acc']:.1%}")
        print(f"  Low Timing OOS Acc: {results['low_timing']['oos_acc']:.1%}")
        print(f"  Combined Curve RMSE: {results['curve_distance']['combined_rmse']:.4f}")
    
    print("\n" + "="*70)
    print("ALL PHASES COMPLETE")
    print("="*70)
