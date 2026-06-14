"""Command-line entrypoint / 命令行入口。

This module translates user-supplied CLI arguments into `NetNomosMiner`
method calls.
本模块负责把用户输入的命令行参数转换为 `NetNomosMiner` 的方法调用。

It does not implement rule-mining algorithms itself. Instead, it handles:
它本身不实现规则挖掘算法，而是负责以下工作：

1. Defining subcommands and arguments.
   定义子命令和参数。
2. Converting parsed CLI arguments into `NetNomosMiner` call parameters.
   把解析后的命令行参数整理成 `NetNomosMiner` 所需的调用参数。
3. Dispatching requests to prepare / learn / validate / interpret / entails.
   把请求分发到 prepare / learn / validate / interpret / entails 等流程。
4. Rendering results to stdout or files in JSON or plain text.
   将结果以 JSON 或纯文本形式输出到终端或文件。

When reading this file, you can think of it as the system shell:
阅读这个文件时，可以把它看成系统外壳：
- algorithmic core lives in `api.py`, `projection.py`, `learners/`, and `theory.py`
  算法核心位于 `api.py`、`projection.py`、`learners/`、`theory.py`
- this file answers how users trigger those capabilities from the command line
  这个文件解决的是用户如何通过命令行触发这些核心能力
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rich import print as rich_print
from rich.json import JSON

from netnomos.api import NetNomosMiner
from netnomos.dsl import parse_formula
from netnomos.logging_utils import configure_logging
from netnomos.specs import (
    GrammarSpec,
    HittingSetBackend,
    LearnerKind,
    load_dataset_spec,
    load_grammar_spec,
)


class CliFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """CLI help formatter / CLI 帮助格式器。

    It combines:
    它组合了两种 formatter：
    - `ArgumentDefaultsHelpFormatter`: shows default values automatically
      `ArgumentDefaultsHelpFormatter`：自动展示默认值
    - `RawDescriptionHelpFormatter`: preserves multiline descriptions/examples
      `RawDescriptionHelpFormatter`：保留多行描述和示例格式
    """

    pass


CLI_DESCRIPTION = (
    "Inspect specs, prepare datasets, learn rules, validate rule sets, "
    "interpret saved artifacts, and run entailment queries.\n"
    "查看配置、准备数据集、学习规则、验证规则集、解释已有工件，并执行蕴含查询。"
)


CLI_EPILOG = """Examples / 示例:
  1. Learn rules from CIDDS / 从 CIDDS 学习规则
     netn learn --dataset-spec examples/datasets/cidds.json --grammar-spec examples/grammars/network_flow.json --input data/cidds_wk2_normal_10k.csv

  2. Learn rules from Netflix PCAP / 从 Netflix PCAP 学习规则
     netn learn --dataset-spec examples/datasets/pcap_tcp.json --grammar-spec examples/grammars/pcap_window.json --input data/netflix.pcap

  3. Run an entailment query on saved rules / 对已保存规则执行蕴含查询
     netn entails --dataset-spec examples/datasets/cidds.json --grammar-spec examples/grammars/network_flow.json --rules runs/<run>/rules.json --query "Packets * 65535 >= Bytes"
"""


def add_dataset_spec_arg(parser: argparse.ArgumentParser) -> None:
    """Add the dataset spec argument / 添加数据集配置参数。"""

    parser.add_argument(
        "--dataset-spec",
        required=True,
        help=(
            "Path to a dataset schema JSON file.\n"
            "数据集 schema JSON 文件路径。"
        ),
    )


def add_grammar_spec_arg(parser: argparse.ArgumentParser) -> None:
    """Add the grammar spec argument / 添加语法配置参数。"""

    parser.add_argument(
        "--grammar-spec",
        required=True,
        help=(
            "Path to a grammar JSON file.\n"
            "语法配置 JSON 文件路径。"
        ),
    )


def add_input_arg(parser: argparse.ArgumentParser) -> None:
    """Add the input override argument / 添加输入数据覆盖参数。"""

    parser.add_argument(
        "--input",
        help=(
            "Override the dataset spec source path for this command.\n"
            "覆盖当前命令使用的数据输入路径，优先级高于 dataset spec 中的默认 source.path。"
        ),
    )


def add_limit_arg(parser: argparse.ArgumentParser) -> None:
    """Add the input row/packet limit argument / 添加输入规模限制参数。"""

    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Maximum number of raw input rows or packets to load before preprocessing.\n"
            "预处理前最多加载多少条原始行或多少个原始数据包。"
        ),
    )


def add_learner_arg(parser: argparse.ArgumentParser) -> None:
    """Add the learner selector argument / 添加学习器选择参数。"""

    parser.add_argument(
        "--learner",
        choices=[item.value for item in LearnerKind],
        default=LearnerKind.HITTING_SET.value,
        help=(
            "Rule-learning backend to use when learning rules.\n"
            "选择规则学习器，当前支持 hitting-set 与 tree。"
        ),
    )


def add_stall_timeout_arg(parser: argparse.ArgumentParser) -> None:
    """Add the stall-timeout argument / 添加停滞超时参数。"""

    parser.add_argument(
        "--stall-timeout",
        type=float,
        help=(
            "Stop the hitting-set search after this many seconds without discovering a new rule; "
            "ignored by the tree learner.\n"
            "若 hitting-set 学习器在给定秒数内未发现新规则，则提前停止；tree 学习器会忽略此参数。"
        ),
    )


def add_hittingset_backend_arg(parser: argparse.ArgumentParser) -> None:
    """Add the hitting-set backend selector / 添加 hitting-set 后端参数。"""

    parser.add_argument(
        "--hittingset-backend",
        choices=[item.value for item in HittingSetBackend],
        default=HittingSetBackend.AUTO.value,
        help=(
            "Implementation for the hitting-set learner: native uses the pybind11 C++ core, "
            "python keeps the pure Python search, and auto prefers native when available.\n"
            "选择 hitting-set 的实现后端：native 使用 pybind11/C++ 核心，python 使用纯 Python 实现，"
            "auto 表示可用时优先 native。"
        ),
    )


def add_runs_dir_arg(parser: argparse.ArgumentParser) -> None:
    """Add the runs directory argument / 添加运行产物目录参数。"""

    parser.add_argument(
        "--runs-dir",
        default="runs",
        help=(
            "Directory where learning runs and artifacts are written.\n"
            "学习运行结果和工件写入的目录。"
        ),
    )


def add_rules_arg(parser: argparse.ArgumentParser) -> None:
    """Add the existing-rules argument / 添加已有规则工件路径参数。"""

    parser.add_argument(
        "--rules",
        help=(
            "Path to an existing rules.json artifact. When provided, the command skips learning and "
            "operates on those saved rules.\n"
            "已有 rules.json 工件路径。提供该参数时，命令会跳过重新学习，直接基于已保存规则执行操作。"
        ),
    )


def add_query_arg(parser: argparse.ArgumentParser) -> None:
    """Add the entailment query argument / 添加蕴含查询参数。"""

    parser.add_argument(
        "--query",
        required=True,
        help=(
            "Formula string to check for entailment.\n"
            "用于蕴含判断的公式字符串。"
        ),
    )


def add_output_arg(parser: argparse.ArgumentParser) -> None:
    """Add the output file argument / 添加输出文件参数。"""

    parser.add_argument(
        "--output",
        help=(
            "Write the command output to this file instead of stdout when supported.\n"
            "在支持的命令中，将输出写入指定文件而不是标准输出。"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the full CLI parser / 构造完整 CLI 解析器。"""

    parser = argparse.ArgumentParser(
        prog="netn",
        description=CLI_DESCRIPTION,
        epilog=CLI_EPILOG,
        formatter_class=CliFormatter,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help=(
            "Logging verbosity for diagnostic messages written to stderr.\n"
            "写入标准错误的诊断日志级别。"
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="COMMAND",
        help=(
            "Subcommand to run.\n"
            "要执行的子命令。"
        ),
    )

    show_dataset = subparsers.add_parser(
        "show-dataset",
        help=(
            "Print a dataset schema JSON file.\n"
            "打印数据集 schema JSON。"
        ),
        description=(
            "Load and print a dataset schema exactly as NetNomos sees it.\n"
            "按 NetNomos 实际读取后的形式加载并打印数据集 schema。"
        ),
        formatter_class=CliFormatter,
    )
    add_dataset_spec_arg(show_dataset)

    show_grammar = subparsers.add_parser(
        "show-grammar",
        help=(
            "Print a grammar JSON file.\n"
            "打印语法配置 JSON。"
        ),
        description=(
            "Load and print a grammar exactly as NetNomos sees it.\n"
            "按 NetNomos 实际读取后的形式加载并打印语法配置。"
        ),
        formatter_class=CliFormatter,
    )
    add_grammar_spec_arg(show_grammar)

    prepare = subparsers.add_parser(
        "prepare",
        help=(
            "Load and materialize a dataset.\n"
            "加载并物化准备后的数据集。"
        ),
        description=(
            "Load a dataset, apply preprocessing, build context windows and derived variables, "
            "and print the resulting schema summary.\n"
            "加载数据集，执行预处理、构建上下文窗口和派生变量，并输出准备后的 schema 摘要。"
        ),
        formatter_class=CliFormatter,
    )
    add_dataset_spec_arg(prepare)
    add_input_arg(prepare)
    add_limit_arg(prepare)

    learn = subparsers.add_parser(
        "learn",
        help=(
            "Generate predicates and learn rules.\n"
            "生成谓词并学习规则。"
        ),
        description=(
            "Generate predicates and learn rules from a dataset using a grammar and a selected learner.\n"
            "根据数据集配置、语法配置和指定学习器生成谓词并学习规则。"
        ),
        formatter_class=CliFormatter,
    )
    add_dataset_spec_arg(learn)
    add_grammar_spec_arg(learn)
    add_input_arg(learn)
    add_limit_arg(learn)
    add_learner_arg(learn)
    add_stall_timeout_arg(learn)
    add_hittingset_backend_arg(learn)
    add_runs_dir_arg(learn)

    mine = subparsers.add_parser(
        "mine",
        help=argparse.SUPPRESS,
        description=(
            "Deprecated alias for `learn`.\n"
            "`learn` 的历史兼容别名，已弃用。"
        ),
        formatter_class=CliFormatter,
    )
    add_dataset_spec_arg(mine)
    add_grammar_spec_arg(mine)
    add_input_arg(mine)
    add_limit_arg(mine)
    add_learner_arg(mine)
    add_stall_timeout_arg(mine)
    add_hittingset_backend_arg(mine)
    add_runs_dir_arg(mine)
    subparsers._choices_actions = [action for action in subparsers._choices_actions if action.dest != "mine"]

    validate = subparsers.add_parser(
        "validate",
        help=(
            "Validate a learned or saved rule set against data.\n"
            "在数据上验证学习得到或已保存的规则集。"
        ),
        description=(
            "Validate saved rules.json artifacts, or learn a fresh rule set first and then validate it "
            "against the prepared dataset.\n"
            "验证已保存的 rules.json 工件；如果未提供规则文件，则先学习一套新规则，再在准备后的数据集上验证。"
        ),
        formatter_class=CliFormatter,
    )
    add_dataset_spec_arg(validate)
    add_grammar_spec_arg(validate)
    add_input_arg(validate)
    add_limit_arg(validate)
    add_rules_arg(validate)
    add_learner_arg(validate)
    add_stall_timeout_arg(validate)
    add_hittingset_backend_arg(validate)
    add_runs_dir_arg(validate)

    interpret = subparsers.add_parser(
        "interpret",
        help=(
            "Render rules into human-readable formulas.\n"
            "把规则渲染成人类可读公式。"
        ),
        description=(
            "Interpret saved rules.json artifacts, or learn a fresh rule set first and then print the "
            "interpreted formulas.\n"
            "解释已保存的 rules.json 工件；如果未提供规则文件，则先学习新规则，再输出解释后的公式文本。"
        ),
        formatter_class=CliFormatter,
    )
    add_dataset_spec_arg(interpret)
    add_grammar_spec_arg(interpret)
    add_input_arg(interpret)
    add_limit_arg(interpret)
    add_rules_arg(interpret)
    add_learner_arg(interpret)
    add_stall_timeout_arg(interpret)
    add_hittingset_backend_arg(interpret)
    add_runs_dir_arg(interpret)
    add_output_arg(interpret)

    entails = subparsers.add_parser(
        "entails",
        help=(
            "Check whether a query is entailed by a rule set.\n"
            "检查某个查询是否被规则集蕴含。"
        ),
        description=(
            "Run a theory-level entailment query against saved rules.json artifacts, or learn a fresh "
            "rule set first and then ask the query.\n"
            "对已保存的 rules.json 工件执行理论层面的蕴含查询；如果未提供规则文件，则先学习新规则，再执行查询。"
        ),
        formatter_class=CliFormatter,
    )
    add_dataset_spec_arg(entails)
    add_grammar_spec_arg(entails)
    add_input_arg(entails)
    add_limit_arg(entails)
    add_rules_arg(entails)
    add_query_arg(entails)
    add_learner_arg(entails)
    add_stall_timeout_arg(entails)
    add_hittingset_backend_arg(entails)
    add_runs_dir_arg(entails)

    return parser


def write_stdout(text: str) -> None:
    """Write to stdout with a trailing newline / 写标准输出并保证结尾换行。"""

    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def write_json(data: object) -> None:
    """Write pretty JSON to stdout / 将格式化 JSON 写到标准输出。"""

    write_stdout(json.dumps(data, indent=2))


def write_rich_json(data: object) -> None:
    """Write rich-formatted JSON / 用 rich 渲染 JSON 输出。"""

    rich_print(JSON.from_data(data, indent=2))


def write_text_file(path: str | Path, text: str) -> None:
    """Write text to a file / 把文本写入文件。"""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text if text.endswith("\n") else f"{text}\n")


def build_fit_kwargs(args: argparse.Namespace) -> dict[str, object]:
    """Build `NetNomosMiner.fit()` kwargs / 构造 `NetNomosMiner.fit()` 所需参数。"""

    return {
        "input_path": getattr(args, "input", None),
        "learner": getattr(args, "learner", LearnerKind.HITTING_SET.value),
        "limit": getattr(args, "limit", None),
        "stall_timeout": getattr(args, "stall_timeout", None),
        "hitting_set_backend": getattr(args, "hittingset_backend", HittingSetBackend.AUTO.value),
    }


def build_miner(args: argparse.Namespace) -> NetNomosMiner:
    """Construct the miner from parsed args / 根据解析结果构造 miner。"""

    return NetNomosMiner.from_files(
        dataset_spec=args.dataset_spec,
        grammar_spec=args.grammar_spec,
        runs_dir=getattr(args, "runs_dir", "runs"),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI main entrypoint / CLI 主入口。"""

    # 第 1 步：解析命令行参数。
    # 这里会根据 build_parser() 中定义的顶层命令、子命令和参数规则，
    # 把用户输入转换成 argparse.Namespace。
    # 如果用户参数不合法，argparse 会直接打印帮助并终止进程，
    # 因此能走到后面的代码，说明参数结构已经通过基础校验。
    args = build_parser().parse_args(argv)

    # 第 2 步：尽早初始化日志系统。
    # 之所以在真正执行任何业务逻辑之前做这件事，是因为后续的数据加载、
    # 规则学习、告警信息、早停信息都依赖统一的 logger 输出。
    # 这里从命令行读取日志级别，使用户可以通过 --log-level 控制调试信息密度。
    configure_logging(getattr(args, "log_level", "INFO"))

    # 第 3 步：处理“只读型”轻量命令。
    # 这类命令只需要读取配置文件并打印，不需要构造 NetNomosMiner，
    # 也不会触发数据准备、谓词生成、规则学习等较重流程。
    if args.command == "show-dataset":
        # 读取 dataset spec，直接输出格式化 JSON。
        # 这里输出的是 Pydantic 校验后的结构，因此可用于确认：
        # 1. 文件能否被成功解析；
        # 2. 最终进入系统的配置长什么样。
        spec = load_dataset_spec(args.dataset_spec)
        write_stdout(spec.model_dump_json(indent=2))
        return 0

    if args.command == "show-grammar":
        # 与 show-dataset 类似，但这里针对 grammar spec。
        # 适合在学习前先检查语法空间是否符合预期。
        spec = load_grammar_spec(args.grammar_spec)
        write_stdout(spec.model_dump_json(indent=2))
        return 0

    if args.command == "prepare":
        # prepare 命令只关注“数据准备”阶段：
        # - 加载原始数据
        # - 执行预处理
        # - 构造上下文窗口
        # - 生成派生变量
        # 它不会进入谓词生成和规则学习阶段。
        spec = load_dataset_spec(args.dataset_spec)

        # NetNomosMiner 的构造函数要求同时提供 dataset_spec 和 grammar_spec。
        # 但 prepare 本身根本不会用到 grammar，因此这里传入一个占位的 GrammarSpec，
        # 只是为了复用 NetNomosMiner.prepare() 这条已有代码路径。
        miner = NetNomosMiner(spec, GrammarSpec(name="prepare-only"))

        # 执行数据准备，并允许用户通过 --input / --limit 临时覆盖默认输入。
        prepared = miner.prepare(input_path=args.input, limit=args.limit)

        # 将准备后的关键摘要输出为 JSON，而不是把整张表直接打印出来。
        # 这里重点暴露的是：
        # - 行数
        # - 列名
        # - 上下文族
        # - 数据源类型
        # - 配置排除字段与自动排除字段
        # 这些信息足以帮助用户快速判断 prepare 流程是否符合预期。
        write_json({
            "rows": len(prepared.dataframe),
            "columns": list(prepared.dataframe.columns),
            "context_families": prepared.context_families,
            "source_type": prepared.source_type.value,
            "configured_exclude_fields": prepared.configured_exclude_fields,
            "auto_excluded_fields": prepared.excluded_fields,
            "excluded_fields": prepared.effective_excluded_fields,
        })
        return 0

    # 第 4 步：其余命令都依赖完整的 miner，因此统一在这里构造。
    # 这些命令至少需要知道：
    # - 数据集配置
    # - 语法配置
    # - runs 产物目录
    # 后面会根据具体命令决定是否真正触发 fit()。
    miner = build_miner(args)

    if args.command in {"learn", "mine"}:
        # learn / mine 是“完整学习流程”的入口。
        # main 本身不展开算法细节，而是把 CLI 参数整理后全部交给 miner.fit()。
        # fit() 内部会完成：
        # 1. 数据准备
        # 2. 谓词生成
        # 3. 规则学习
        # 4. 工件落盘
        result = miner.fit(**build_fit_kwargs(args))

        # 这里返回的是运行摘要，而不是完整规则内容。
        # 设计目的有两个：
        # 1. 终端输出保持简洁，避免一次性刷出大量规则文本；
        # 2. 让用户先知道运行目录、规则数量、谓词数量和学习元信息，
        #    再按需去 runs/<run>/ 下查看详细工件。
        write_rich_json({
            "run_dir": str(result.run_dir),
            "rules": len(result.rules),
            "predicates": len(result.predicates),
            "fit_metadata": result.fit_metadata,
            "configured_exclude_fields": result.prepared.configured_exclude_fields,
            "auto_excluded_fields": result.prepared.excluded_fields,
            "excluded_fields": result.prepared.effective_excluded_fields,
        })
        return 0

    if args.command == "validate":
        if args.rules:
            # validate 分两种模式：
            # 模式 A：用户提供现成 rules.json，此时直接加载规则并验证；
            # 模式 B：用户不提供规则文件，此时先学习一套规则，再验证。
            #
            # 当前分支属于模式 A。这样可以避免每次验证都重新学习，
            # 特别适合对同一套规则反复切换数据集或采样规模做校验。
            rules = miner.load_rules(args.rules)
            write_json(miner.validate_rules(rules, input_path=args.input, limit=args.limit))
            return 0

        # 当前分支属于模式 B。
        # 先执行 fit()，让 miner.last_result 持有刚学习出的规则与 prepared dataset，
        # 然后再调用 miner.validate() 对“最近一次 fit 的结果”做验证。
        miner.fit(**build_fit_kwargs(args))
        write_json(miner.validate())
        return 0

    if args.command == "interpret":
        if args.rules:
            # interpret 同样支持“已有规则”模式。
            # 这里先读取结构化 rules.json，再尝试加载同目录下的 semantic_values.json。
            # 这样解释阶段就能把数值常量显示成 p50 / top1 等语义标签，
            # 而不是只展示原始数值。
            rules = miner.load_rules(args.rules)
            semantic_values = miner.load_semantic_values_for_rules(args.rules)
            lines = miner.interpret_rules(
                rules,
                input_path=args.input,
                limit=args.limit,
                semantic_values=semantic_values,
            )

            # 解释结果最终是字符串列表，这里统一拼接成多行文本。
            text = "\n".join(lines)
            if args.output:
                # 若用户指定 --output，则优先落盘，并回一个简要 JSON 摘要，
                # 告诉用户文件写到了哪里、共输出了多少条规则。
                write_text_file(args.output, text)
                write_json({
                    "output": str(Path(args.output)),
                    "rules": len(lines),
                })
                return 0

            # 未指定输出文件时，直接把解释文本打印到终端。
            write_stdout(text)
            return 0

        # 若未提供 rules.json，则 interpret 会先学习，再解释刚学习出的规则。
        # 这种模式适合“一次命令跑完整流程并直接查看可读规则”。
        miner.fit(**build_fit_kwargs(args))
        lines = miner.interpret()
        text = "\n".join(lines)
        if args.output:
            # 与上面的已有规则模式保持同样的输出行为。
            write_text_file(args.output, text)
            write_json({
                "output": str(Path(args.output)),
                "rules": len(lines),
            })
            return 0
        write_stdout(text)
        return 0

    if args.command == "entails":
        if args.rules:
            # entails 也支持两种模式。
            # 当前分支是“已有规则”模式：直接对指定规则集做理论级蕴含判断。
            # 这适合把一套保存下来的规则当作理论库重复查询。
            rules = miner.load_rules(args.rules)
            entailed = miner.entails_with_rules(args.query, rules, input_path=args.input, limit=args.limit)
        else:
            # 未提供规则时，先学习，再基于刚学习出的理论执行查询。
            # 注意这里把 args.query 交给 parse_formula() 解析成 AST，
            # 然后传入 miner.entails() 做逻辑蕴含检查。
            miner.fit(**build_fit_kwargs(args))
            entailed = miner.entails(parse_formula(args.query))

        # entails 命令只返回一个非常小的结果对象：
        # {"entailed": true/false}
        # 这样更方便脚本调用和自动化判断。
        write_json({
            "entailed": entailed,
        })
        return 0

    # 理论上所有合法子命令都会在上面的分支中 return 0。
    # 这里保留一个兜底返回 1，目的是：
    # 1. 防止未来新增命令时遗漏分支；
    # 2. 一旦执行流意外落到这里，调用者可以通过非零退出码感知异常。
    return 1
