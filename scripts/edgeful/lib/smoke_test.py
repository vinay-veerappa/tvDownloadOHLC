#!/usr/bin/env python3
"""
Smoke Test for Phase 1 Library — Verify all modules import and initialize correctly

This test does NOT require full historical data or parquet files.
It only checks that:
  1. All modules import without errors
  2. DataLoader initializes
  3. Dataclasses are properly defined
  4. Filter dimensions are discoverable

Usage:
    python scripts/edgeful/lib/smoke_test.py
"""

import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

def test_imports():
    """Test that all modules import successfully."""
    print("Testing imports...")
    
    try:
        from scripts.edgeful.lib.data_loader import DataLoader, get_loader
        print("  ✓ data_loader imports OK")
    except Exception as e:
        print(f"  ✗ data_loader import failed: {e}")
        return False
    
    try:
        from scripts.edgeful.lib.session_tagger import tag_session, SESSION_WINDOWS
        print("  ✓ session_tagger imports OK")
    except Exception as e:
        print(f"  ✗ session_tagger import failed: {e}")
        return False
    
    try:
        from scripts.edgeful.lib.context import (
            DailyContext, DailyContextBuilder, 
            EVENT_CATEGORIES, classify_event_type, classify_event_types
        )
        print("  ✓ context imports OK")
    except Exception as e:
        print(f"  ✗ context import failed: {e}")
        return False
    
    try:
        from scripts.edgeful.lib.filters import (
            FilterDimension, UNIVERSAL_FILTERS, MACRO_FILTERS, RANGE_FILTERS,
            get_filter_by_name, build_filter_sql_expression
        )
        print("  ✓ filters imports OK")
    except Exception as e:
        print(f"  ✗ filters import failed: {e}")
        return False
    
    return True


def test_dataloader_init():
    """Test DataLoader initialization."""
    print("\nTesting DataLoader initialization...")
    
    try:
        from scripts.edgeful.lib.data_loader import DataLoader
        loader = DataLoader()
        print(f"  ✓ DataLoader initialized (data_root={loader.data_root})")
        return True
    except Exception as e:
        print(f"  ✗ DataLoader init failed: {e}")
        return False


def test_dataclass_fields():
    """Test that DailyContext dataclass has expected fields."""
    print("\nTesting DailyContext dataclass...")
    
    try:
        from scripts.edgeful.lib.context import DailyContext
        fields = list(DailyContext.__dataclass_fields__.keys())
        print(f"  ✓ DailyContext has {len(fields)} fields")
        
        # Spot-check key fields
        expected_fields = [
            "symbol", "trading_date", "vix_close", "vix_regime",
            "pdh", "pdl", "gap_size_pct", "gap_direction",
            "atr_14d", "session_direction", "event_type", "event_types"
        ]
        missing = [f for f in expected_fields if f not in fields]
        if missing:
            print(f"  ✗ Missing fields: {missing}")
            return False
        
        print(f"  ✓ All expected fields present")
        return True
    except Exception as e:
        print(f"  ✗ DailyContext check failed: {e}")
        return False


def test_event_categories():
    """Test event category definitions."""
    print("\nTesting event categories...")
    
    try:
        from scripts.edgeful.lib.context import (
            EVENT_CATEGORIES, classify_event_type, classify_event_types
        )
        
        num_categories = len(EVENT_CATEGORIES)
        print(f"  ✓ {num_categories} event categories defined")
        
        if num_categories < 20:
            print(f"  ⚠ Expected 20 categories, found {num_categories}")
        
        # Test classification functions
        test_event = "FOMC Decision"
        primary = classify_event_type(test_event)
        all_matches = classify_event_types(test_event)
        
        print(f"  ✓ classify_event_type('{test_event}') = {primary}")
        print(f"  ✓ classify_event_types('{test_event}') = {all_matches}")
        return True
    except Exception as e:
        print(f"  ✗ Event categories check failed: {e}")
        return False


def test_filters():
    """Test filter dimensions."""
    print("\nTesting filter dimensions...")
    
    try:
        from scripts.edgeful.lib.filters import (
            UNIVERSAL_FILTERS, MACRO_FILTERS, RANGE_FILTERS, get_filter_by_name
        )
        
        print(f"  ✓ {len(UNIVERSAL_FILTERS)} universal filters")
        print(f"  ✓ {len(MACRO_FILTERS)} macro filters")
        print(f"  ✓ {len(RANGE_FILTERS)} range filters")
        
        # Test lookup
        vix_filter = get_filter_by_name("vix_regime", UNIVERSAL_FILTERS)
        if vix_filter:
            print(f"  ✓ Found vix_regime filter: {vix_filter.values}")
        else:
            print(f"  ✗ Could not find vix_regime filter")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ Filters check failed: {e}")
        return False


def test_session_windows():
    """Test session window definitions."""
    print("\nTesting session windows...")
    
    try:
        from scripts.edgeful.lib.session_tagger import SESSION_WINDOWS
        
        num_sessions = len(SESSION_WINDOWS)
        print(f"  ✓ {num_sessions} session types defined")
        
        if num_sessions != 7:
            print(f"  ⚠ Expected 7 sessions, found {num_sessions}")
        
        for session_name, window in SESSION_WINDOWS.items():
            start, end = window  # Unpack tuple
            print(f"    - {session_name}: {start}–{end}")
        
        return True
    except Exception as e:
        print(f"  ✗ Session windows check failed: {e}")
        return False


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("Phase 1 Library Smoke Test")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_dataloader_init,
        test_dataclass_fields,
        test_event_categories,
        test_filters,
        test_session_windows,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All smoke tests passed! Ready for generation.\n")
        return 0
    else:
        print("\n✗ Some tests failed. Check errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
