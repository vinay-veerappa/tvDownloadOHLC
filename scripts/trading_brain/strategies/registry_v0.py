"""Strategy Registry V0 loader and validator (Milestone 0.5).

Loads frozen JSON strategy definitions anchored to REPO_ROOT and detects content hash drift.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import REPO_ROOT, get_db_connection

ARTIFACTS_DIR = REPO_ROOT / "scripts" / "trading_brain" / "strategies" / "artifacts"


class StrategyVersionDriftError(Exception):
    """Raised when an existing strategy version's definition has drifted from recorded content hash."""
    pass


def load_strategy_artifact(json_path: Path) -> Dict[str, Any]:
    """Loads and validates a frozen strategy JSON definition."""
    content = json_path.read_text(encoding="utf-8")
    data = json.loads(content)
    
    required_fields = [
        "strategy_version_id", "strategy_family", "version_tag",
        "ticker_scope", "required_providers", "session_window_et",
        "trigger_expression", "decision_timing", "entry_convention",
        "stop_loss_bps", "target_1_bps", "status"
    ]
    for rf in required_fields:
        if rf not in data:
            raise ValueError(f"Strategy artifact {json_path.name} missing required field '{rf}'")
            
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    data["content_hash"] = f"sha256:{content_hash}"
    data["rules_doc_path"] = str(json_path)
    return data


def register_all_v0_strategies(
    artifacts_dir: Optional[Path] = None,
    db_path: Optional[Union[str, Path]] = None
) -> List[str]:
    """Registers all frozen strategy definitions from artifacts directory into database with drift detection."""
    target_dir = artifacts_dir or ARTIFACTS_DIR
    if not target_dir.is_absolute():
        target_dir = REPO_ROOT / target_dir
        
    registered = []
    
    for json_file in target_dir.glob("*.json"):
        strat_data = load_strategy_artifact(json_file)
        strat_id = strat_data["strategy_version_id"]
        new_hash = strat_data["content_hash"]
        
        with get_db_connection(db_path) as conn:
            cur = conn.execute("SELECT content_hash FROM strategy_versions WHERE strategy_version_id = ?;", (strat_id,))
            row = cur.fetchone()
            if row:
                if row["content_hash"] != new_hash:
                    raise StrategyVersionDriftError(
                        f"Strategy '{strat_id}' definition has drifted! Recorded: {row['content_hash']}, Artifact: {new_hash}"
                    )
            else:
                conn.execute(
                    """
                    INSERT INTO strategy_versions (
                        strategy_version_id, strategy_family, version_tag,
                        content_hash, rules_doc_path, execution_policy_json, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        strat_id,
                        strat_data["strategy_family"],
                        strat_data["version_tag"],
                        new_hash,
                        strat_data["rules_doc_path"],
                        json.dumps({
                            "stop_loss_bps": strat_data["stop_loss_bps"],
                            "target_1_bps": strat_data["target_1_bps"],
                            "target_2_bps": strat_data.get("target_2_bps", 30.0),
                            "cost_model_bps": strat_data.get("cost_model_bps", 2.0)
                        }),
                        strat_data["status"]
                    )
                )
        registered.append(strat_id)
        
    return registered
