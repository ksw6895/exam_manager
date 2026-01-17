"""
Repository verification script for refactoring safety.

This script runs basic validation checks to ensure the repository is in a good state
before and after refactoring changes.

Usage:
  python scripts/verify_repo.py                    # Basic compileall check
  python scripts/verify_repo.py --db data/dev.db    # Include DB migrations/FTS check
  python scripts/verify_repo.py --all               # All checks (compileall + DB)

Exit codes:
  0 - All checks passed
  1 - One or more checks failed
"""

from __future__ import annotations

import argparse
import compileall
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


def _compile_check() -> bool:
    """Run compileall on Python source files."""
    print("Running compileall check...")
    targets = [
        ROOT_DIR / "app",
        ROOT_DIR / "scripts",
        ROOT_DIR / "run.py",
        ROOT_DIR / "run_local_admin.py",
    ]

    for target in targets:
        if not target.exists():
            print(f"  [SKIP] {target} does not exist")
            continue

        result = compileall.compile_dir(
            target,
            force=True,
            quiet=1,
        )
        if not result:
            print(f"  [FAIL] Compilation failed for {target}")
            return False
        print(f"  [OK] {target}")

    print("[PASS] All Python files compiled successfully")
    return True


def _db_check(db_path: Path) -> bool:
    """Run DB migrations and FTS check on specified database."""
    if not db_path.exists():
        print(f"  [SKIP] Database not found: {db_path}")
        print(
            "  Use 'python scripts/clone_db.py --db data/exam.db --out data/dev.db' to create dev DB"
        )
        return True  # Not a failure - just skip

    print(f"\nRunning DB migration check for {db_path}...")

    try:
        from scripts.run_migrations import run_migrations
        from scripts.init_fts import init_fts

        # Run migrations
        count = run_migrations(db_path)
        if count > 0:
            print(f"  [INFO] Applied {count} migration(s)")
        else:
            print("  [INFO] No pending migrations")

        # Run FTS sync (doesn't rebuild, just syncs)
        init_fts(db_path, rebuild=False)
        print("  [OK] FTS sync completed")

        print("[PASS] DB checks passed")
        return True
    except Exception as e:
        print(f"  [FAIL] DB check failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify repository state for refactoring safety."
    )
    parser.add_argument(
        "--db",
        type=Path,
        help="Path to SQLite DB for migration/FTS check (e.g., data/dev.db)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all checks including DB (uses data/dev.db if --db not specified)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("EXAM MANAGER - REPOSITORY VERIFICATION")
    print("=" * 60)

    # Always run compileall
    if not _compile_check():
        print("\n[FAIL] Compile check failed")
        return 1

    # Run DB checks if requested
    if args.all or args.db:
        db_path = args.db or (ROOT_DIR / "data" / "dev.db")
        if not _db_check(db_path):
            print("\n[FAIL] DB check failed")
            return 1

    print("\n" + "=" * 60)
    print("[SUCCESS] All verification checks passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
