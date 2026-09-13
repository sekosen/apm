"""Regression coverage for #2969: symlinked files match applyTo by tree
position, not by resolving to their physical target.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apm_cli.compilation.context_optimizer import ContextOptimizer
from apm_cli.primitives.models import Instruction


def _touch(base: Path, rel: str) -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()


def _symlink(base: Path, rel: str, target: Path) -> Path:
    link = base / rel
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation not supported on this platform")
    return link


class TestSymlinkedFileMatchesByTreePosition:
    """``_file_matches_pattern`` matches on tree position, not physical target."""

    def test_symlink_to_outside_target_matches_by_tree_position(self, tmp_path: Path) -> None:
        outside_target = tmp_path.parent / f"{tmp_path.name}-external-source.ts"
        outside_target.touch()
        link = _symlink(tmp_path, "src/components/Button.ts", outside_target)

        optimizer = ContextOptimizer(base_dir=str(tmp_path))

        assert optimizer._file_matches_pattern(link, "src/**/*.ts") is True

    def test_symlink_matches_by_where_it_appears_not_where_target_lives(
        self, tmp_path: Path
    ) -> None:
        _touch(tmp_path, "vendor/real/Button.ts")
        link = _symlink(
            tmp_path, "src/components/Button.ts", tmp_path / "vendor" / "real" / "Button.ts"
        )

        optimizer = ContextOptimizer(base_dir=str(tmp_path))

        assert optimizer._file_matches_pattern(link, "src/**/*.ts") is True
        assert optimizer._file_matches_pattern(link, "vendor/**/*.ts") is False

    def test_placement_includes_symlinked_file_under_its_tree_position(
        self, tmp_path: Path
    ) -> None:
        outside_target = tmp_path.parent / f"{tmp_path.name}-external-source.ts"
        outside_target.touch()
        _symlink(tmp_path, "src/components/Button.ts", outside_target)

        optimizer = ContextOptimizer(base_dir=str(tmp_path))
        instruction = Instruction(
            name="ts-standards",
            file_path=Path("ts.instructions.md"),
            description="TypeScript standards",
            apply_to="src/**/*.ts",
            content="TS standards",
        )

        result = optimizer.optimize_instruction_placement([instruction])

        assert optimizer._pattern_cache["src/**/*.ts"] == {tmp_path / "src" / "components"}
        assert sum(len(instrs) for instrs in result.values()) == 1

    def test_symlink_with_missing_target_is_excluded(self, tmp_path: Path) -> None:
        # is_file() follows the link to check the target exists.
        dangling_target = tmp_path.parent / f"{tmp_path.name}-does-not-exist.ts"
        link = _symlink(tmp_path, "src/components/Ghost.ts", dangling_target)

        optimizer = ContextOptimizer(base_dir=str(tmp_path))
        instruction = Instruction(
            name="ts-standards",
            file_path=Path("ts.instructions.md"),
            description="TypeScript standards",
            apply_to="src/**/*.ts",
            content="TS standards",
        )

        result = optimizer.optimize_instruction_placement([instruction])

        assert link not in optimizer._files_by_directory.get(link.parent, [])
        placed_dirs = {directory for directory, instrs in result.items() if instrs}
        assert tmp_path / "src" / "components" not in placed_dirs
