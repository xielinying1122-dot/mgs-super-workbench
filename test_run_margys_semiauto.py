import csv
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
RUNNER = ROOT / "run_margys_semiauto.sh"


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)


def build_valid_exports(directory: Path) -> dict[str, Path]:
    creative = directory / "creative.csv"
    note = directory / "note.csv"
    audience = directory / "audience.csv"
    keyword = directory / "keyword.csv"

    write_csv(
        creative,
        [
            ["时间", "创意ID", "创意名称", "消费", "行业商品进店量30日", "行业商品GMV（30日)"],
            ["合计1条记录", "-", "-", "100", "10", "300"],
            ["2026-09-01", "creative-1", "创意A", "100", "10", "300"],
        ],
    )
    write_csv(
        note,
        [
            ["时间", "笔记ID", "消费", "行业商品进店量30日", "行业商品GMV（30日)"],
            ["合计1条记录", "-", "100", "10", "300"],
            ["2026-09-01", "note-1", "100", "10", "300"],
        ],
    )
    write_csv(
        audience,
        [
            ["日期", "人群包ID", "人群包名称", "消费", "店铺访问量(30日)", "店铺成交ROI(30日)"],
            ["合计1条记录", "-", "-", "100", "10", "3"],
            ["20260901", "audience-1", "人群A", "100", "10", "3"],
        ],
    )
    write_csv(
        keyword,
        [
            ["时间", "搜索主题", "消费", "行业商品进店量30日", "行业商品GMV（30日)"],
            ["合计1条记录", "-", "100", "10", "300"],
            ["2026-09-01", "骨胶原面膜", "100", "10", "300"],
        ],
    )
    return {"creative": creative, "note": note, "audience": audience, "keyword": keyword}


class RunnerTests(unittest.TestCase):
    def test_one_command_builds_workbook_from_four_explicit_exports(self):
        self.assertTrue(RUNNER.is_file(), "一键入口脚本尚未实现")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            exports = build_valid_exports(tmp_path)
            output = tmp_path / "result.xlsx"

            result = subprocess.run(
                [
                    str(RUNNER),
                    "--creative",
                    str(exports["creative"]),
                    "--note",
                    str(exports["note"]),
                    "--audience",
                    str(exports["audience"]),
                    "--keyword",
                    str(exports["keyword"]),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreater(output.stat().st_size, 1000)
            self.assertIn(str(output), result.stdout)

    def test_invalid_input_does_not_replace_existing_workbook(self):
        self.assertTrue(RUNNER.is_file(), "一键入口脚本尚未实现")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            exports = build_valid_exports(tmp_path)
            write_csv(
                exports["keyword"],
                [
                    ["时间", "搜索主题", "消费"],
                    ["2026-09-01", "骨胶原面膜", "100"],
                ],
            )
            output = tmp_path / "result.xlsx"
            output.write_bytes(b"existing-workbook")

            result = subprocess.run(
                [
                    str(RUNNER),
                    "--creative",
                    str(exports["creative"]),
                    "--note",
                    str(exports["note"]),
                    "--audience",
                    str(exports["audience"]),
                    "--keyword",
                    str(exports["keyword"]),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"existing-workbook")


if __name__ == "__main__":
    unittest.main()
