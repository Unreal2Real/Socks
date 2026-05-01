"""XGBoost training pipeline for active learning"""
import json
import os
import pickle
import numpy as np
from typing import List, Dict, Tuple, Optional

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ml', 'model')
MODEL_FILE = os.path.join(MODEL_DIR, 'factory_classifier.pkl')

IMPORTANT_FEATURES = ['gain', 'up_days', 'consol_days', 'elevation', 'peak_ratio',
                       'avg_retrace', 'volatility', 'age_days', 'pre_volatility']


def _features_to_array(features: dict) -> np.ndarray:
    return np.array([features.get(k, 0.0) for k in IMPORTANT_FEATURES], dtype=np.float32)


def train_from_labels(labels: List[dict]) -> Tuple[Optional[object], dict]:
    """Train an XGBoost classifier from labeled data. Returns (model, metrics)."""
    good_labels = [l for l in labels if l.get('label') == 'good' and 'features' in l]
    bad_labels = [l for l in labels if l.get('label') == 'bad' and 'features' in l]

    total = len(good_labels) + len(bad_labels)
    if total < 5:
        return None, {'error': f'need at least 5 labels, got {total}', 'total': total}

    X_list = []
    y_list = []
    for l in good_labels:
        X_list.append(_features_to_array(l['features']))
        y_list.append(1)
    for l in bad_labels:
        X_list.append(_features_to_array(l['features']))
        y_list.append(0)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)

    try:
        from xgboost import XGBClassifier
    except ImportError:
        try:
            from sklearn.ensemble import RandomForestClassifier as XGBClassifier
        except ImportError:
            return None, {'error': 'install xgboost or scikit-learn', 'total': total}

    model = XGBClassifier(
        n_estimators=50, max_depth=3, learning_rate=0.1,
        subsample=0.8, random_state=42
    )
    model.fit(X, y)

    train_acc = float((model.predict(X) == y).mean())

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump({'model': model, 'features': IMPORTANT_FEATURES}, f)

    return model, {
        'total_labels': total,
        'good': len(good_labels),
        'bad': len(bad_labels),
        'train_accuracy': round(train_acc, 3),
    }


def predict(features: dict) -> Optional[float]:
    """Return ML confidence score [0, 1]. Returns None if no model exists."""
    if not os.path.exists(MODEL_FILE):
        return None

    try:
        with open(MODEL_FILE, 'rb') as f:
            data = pickle.load(f)
        model = data['model']
        feature_order = data['features']
    except Exception:
        return None

    arr = np.array([features.get(k, 0.0) for k in feature_order], dtype=np.float32).reshape(1, -1)

    try:
        proba = model.predict_proba(arr)
        return round(float(proba[0, 1]), 4)
    except Exception:
        return None


def get_model_info() -> dict:
    if not os.path.exists(MODEL_FILE):
        return {'exists': False}

    try:
        with open(MODEL_FILE, 'rb') as f:
            data = pickle.load(f)
        return {
            'exists': True,
            'features': data['features'],
            'model_type': type(data['model']).__name__,
        }
    except Exception:
        return {'exists': False, 'error': 'corrupted'}
