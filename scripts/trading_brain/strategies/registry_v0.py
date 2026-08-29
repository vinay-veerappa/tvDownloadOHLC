"""Strategy Registry V0 loader and validator (Milestone 0.5).

Loads frozen JSON strategy definitions from scripts/trading_brain/strategies/artifacts/
and registers them into strategy_versions in trading_brain.sqlite.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import get_db_connection

ARTIFACTS_DIR = Path("scripts/trading_brain/strategies/artifacts")


def load_strategy_artifact(json_path: Path) -> Dict[str, Any]:
    """Loads and validates a frozen strategy JSON definition."""
    content = json_path.read_text(encoding="utf-8")
    data = json.loads(content)
    
    # Verify required schema fields
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
    """Registers all frozen strategy definitions from artifacts directory into database."""
    target_dir = artifacts_dir or ARTIFACTS_DIR
    registered = []
    
    for json_file in target_dir.glob("*.json"):
        strat_data = load_strategy_artifact(json_file)
        strat_id = strat_data["strategy_version_id"]
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO strategy_versions (
                    strategy_version_id, strategy_family, version_tag,
                    content_hash, rules_doc_path, execution_policy_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    strat_id,
                    strat_data["strategy_family"],
                    strat_data["version_tag"],
                    strat_data["content_hash"],
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
