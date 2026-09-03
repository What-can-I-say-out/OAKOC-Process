"""读取 OAKOC 请求并运行十三步流程。"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from oakoc import AnalysisRequest, OAKOCPipeline, RunStatus, demo_analyzer_specs


EXAMPLE_INPUT = Path(__file__).resolve().parent / "examples" / "full_process_request.json"


def load_request(path: Path) -> AnalysisRequest:
    """读取 JSON 请求，并检查内容是否符合 AnalysisRequest 格式。"""

    return AnalysisRequest.model_validate_json(path.read_text(encoding="utf-8"))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """读取输入和输出文件参数。"""

    parser = argparse.ArgumentParser(description="运行 OAKOC 十三步分析流程")
    parser.add_argument(
        "--input",
        type=Path,
        default=EXAMPLE_INPUT,
        help="请求 JSON 文件，默认使用 examples/full_process_request.json",
    )
    parser.add_argument("--output", type=Path, help="保存完整结果的 JSON 文件")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """运行流程；返回 0 表示完成，1 表示分析失败，2 表示输入或文件错误。"""

    args = parse_args(argv)
    try:
        request = load_request(args.input)
        result = OAKOCPipeline(demo_analyzer_specs(), mode="demo").run(request)
        content = result.model_dump_json(indent=2)
        if args.output:
            args.output.write_text(content, encoding="utf-8")
        else:
            print(content)
        return 1 if result.status == RunStatus.FAILED else 0
    except (OSError, ValueError) as exc:
        print(f"OAKOC 执行失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
