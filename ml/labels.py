"""Label storage and management"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime

LABELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ml', 'labels')

os.makedirs(LABELS_DIR, exist_ok=True)
LABELS_FILE = os.path.join(LABELS_DIR, 'labels.jsonl')


def save_label(label: dict):
    label['timestamp'] = datetime.now().isoformat()
    with open(LABELS_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(label, ensure_ascii=False) + '\n')


def load_labels() -> List[dict]:
    if not os.path.exists(LABELS_FILE):
        return []
    labels = []
    with open(LABELS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    labels.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return labels


def get_stats() -> dict:
    labels = load_labels()
    good = sum(1 for l in labels if l.get('label') == 'good')
    bad = sum(1 for l in labels if l.get('label') == 'bad')
    corrected = sum(1 for l in labels if l.get('correct_start') or l.get('correct_peak') or l.get('correct_end'))
    return {
        'total': len(labels),
        'good': good,
        'bad': bad,
        'corrected': corrected,
    }
