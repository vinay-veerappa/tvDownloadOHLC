#!/bin/bash
# strategy_validation/run_all.sh
# Master execution script — run studies in order
#
# Usage:
#   ./run_all.sh                           # run everything for all symbols
#   ./run_all.sh --symbols ES NQ           # specific symbols
#   ./run_all.sh --skip-prep               # skip data prep (already done)
#   ./run_all.sh --study 1                 # run only study 1
#
# Prerequisites:
#   pip install pandas numpy pyarrow fastparquet
#   Place parquet files in ./data/raw/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SYMBOLS=""
SKIP_PREP=false
STUDY=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --symbols) shift; SYMBOLS="--symbols $@"; shift $#;;
        --skip-prep) SKIP_PREP=true; shift;;
        --study) STUDY="$2"; shift 2;;
        *) shift;;
    esac
done

echo "=============================================="
echo "  Strategy Validation Pipeline"
echo "=============================================="
echo ""

# Phase 0: Data Preparation
if [ "$SKIP_PREP" = false ] && [ -z "$STUDY" -o "$STUDY" = "0" ]; then
    echo "[Phase 0] Data Preparation..."
    python scripts/00_data_prep.py $SYMBOLS
    echo ""
fi

# Phase 1: Opening Range Study
if [ -z "$STUDY" -o "$STUDY" = "1" ]; then
    echo "[Phase 1] Opening Range Study..."
    python scripts/01_opening_range_study.py $SYMBOLS
    echo ""
fi

# Phase 2: Session Sweep Study
if [ -z "$STUDY" -o "$STUDY" = "2" ]; then
    echo "[Phase 2] Session Sweep Study..."
    python scripts/02_session_sweep_study.py $SYMBOLS
    echo ""
fi

# Phase 3: Key Level Study
if [ -z "$STUDY" -o "$STUDY" = "3" ]; then
    echo "[Phase 3] Key Level Study..."
    python scripts/03_key_level_study.py $SYMBOLS
    echo ""
fi

# Phase 4: Macro Time Study
if [ -z "$STUDY" -o "$STUDY" = "4" ]; then
    echo "[Phase 4] Macro Time Study..."
    python scripts/04_macro_time_study.py $SYMBOLS
    echo ""
fi

# Phase 5: Weekly Profile Study
if [ -z "$STUDY" -o "$STUDY" = "5" ]; then
    echo "[Phase 5] Weekly Profile Study..."
    python scripts/05_weekly_profile_study.py $SYMBOLS
    echo ""
fi

echo "=============================================="
echo "  All studies complete!"
echo "  Results in: ./results/"
echo "  Derived data in: ./data/derived/"
echo "=============================================="
echo ""
echo "Next: Review results, then run prop simulation:"
echo "  python scripts/06_prop_sim.py --symbol NQ --strategy or_fade"
