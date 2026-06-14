"""基于决策树的蕴含规则学习器。

这个学习器和 hitting-set 学习器不同：
- hitting-set 生成的是析取覆盖规则；
- tree learner 生成的是 implication-style 规则，即 `premise -> target`。

核心流程：
1. projection 阶段已经生成一批候选谓词；
2. 把每个谓词在每一行数据上是否成立，编码成 0/1 特征矩阵；
3. 轮流选择一个谓词作为监督目标 y；
4. 用其他谓词作为 X 训练决策树；
5. 从高纯度正叶子的路径中抽取条件，形成 `premise -> target`。

例如：
- 目标 target：`tcp.flags = SYN`
- 路径条件 premise：`ip.proto = 6 AND tcp.len = 0`
- 输出规则：`(ip.proto = 6 AND tcp.len = 0) -> tcp.flags = SYN`
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from tqdm.auto import tqdm

from netnomos.ast import BoolAnd, BoolNot, Compare, Formula, Implies, formula_to_string
from netnomos.dataset import PreparedDataset
from netnomos.learners.hittingset import LearnedRule
from netnomos.projection import GroundedPredicate
from netnomos.theory import evaluate_formula_df


class EntropyTreeLearner:
    """用决策树学习 implication-style 规则。

    该学习器依赖 scikit-learn 的 `DecisionTreeClassifier`。
    它不直接处理原始字段，而是处理 projection 阶段生成的谓词真假矩阵。
    """

    def __init__(
        self,
        max_depth: int = 4,
        min_samples_leaf: int = 2,
        min_positive_purity: float = 0.95,
        max_rules: int = 250,
    ):
        """初始化树学习器参数。

        参数含义：
        - `max_depth`：树最大深度，也限制 premise 最多包含多少层路径条件；
        - `min_samples_leaf`：叶子最少样本数，避免从极少样本中生成脆弱规则；
        - `min_positive_purity`：正类叶子的最低纯度，越高规则越保守；
        - `max_rules`：最多返回多少条规则。
        """
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.min_positive_purity = min_positive_purity
        self.max_rules = max_rules
        self.last_fit_metadata: dict[str, float | int] = {}

    def fit(self, predicates: list[GroundedPredicate], prepared: PreparedDataset) -> list[LearnedRule]:
        """对每个谓词轮流作为目标，学习一组蕴含规则。

        输入的 `predicates` 已经是可求值的候选谓词。
        本函数会构建一个布尔矩阵：
        - 行：数据样本；
        - 列：谓词；
        - 值：该行是否满足该谓词。

        然后每一列都轮流作为目标 y，其余列作为特征 X。
        """
        try:
            from sklearn.tree import DecisionTreeClassifier
        except ModuleNotFoundError as exc:
            raise RuntimeError("EntropyTreeLearner requires scikit-learn to be installed") from exc

        # 布尔特征矩阵：行对应样本，列对应谓词是否成立。
        # 这里一次性缓存所有谓词求值结果，避免每个 target 训练时重复评估公式。
        matrix = np.column_stack([
            evaluate_formula_df(predicate.formula, prepared).astype(int).to_numpy()
            for predicate in tqdm(predicates, desc="Evaluating tree features", unit=" predicate", disable=None)
        ])
        rules: list[LearnedRule] = []
        for target_index, target in enumerate(tqdm(predicates, desc="Learning tree rules", unit=" target", disable=None)):
            if len(rules) >= self.max_rules:
                break
            y = matrix[:, target_index]
            if y.min() == y.max():
                # 如果目标谓词在所有样本上恒真或恒假，决策树学不到有意义的区分规则。
                continue
            # 不能把目标谓词自己作为特征，否则会学出 target -> target 这种无意义规则。
            feature_indices = [index for index in range(len(predicates)) if index != target_index]
            X = matrix[:, feature_indices]
            clf = DecisionTreeClassifier(
                criterion="entropy",
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                random_state=42,
            )
            clf.fit(X, y)
            tree = clf.tree_

            def walk(node_id: int, conditions: list[tuple[int, bool]]) -> None:
                """深度优先遍历决策树，把高纯度正叶子转成规则。

                `conditions` 记录从根节点走到当前节点经历的路径条件。
                每个元素是 `(local_feature_index, positive)`：
                - positive=True 表示该谓词成立；
                - positive=False 表示该谓词不成立。
                """
                if len(rules) >= self.max_rules:
                    return
                left = tree.children_left[node_id]
                right = tree.children_right[node_id]
                if left == right:
                    # 叶子节点：检查它是否预测 target=True，且纯度足够高。
                    probs = tree.value[node_id][0]
                    if clf.classes_[int(np.argmax(probs))] != 1:
                        return
                    total = float(np.sum(probs))
                    purity = float(np.max(probs) / total) if total else 0.0
                    if purity < self.min_positive_purity:
                        return
                    premise_formula = build_path_formula(conditions, predicates, feature_indices)
                    if premise_formula is None:
                        return
                    # 决策路径作为前提，target 谓词作为结论。
                    formula = Implies(premise_formula, target.formula)
                    support = float(evaluate_formula_df(formula, prepared).mean())
                    rules.append(LearnedRule(
                        rule_id=f"tree{len(rules):05d}",
                        formula=formula,
                        display=formula_to_string(formula),
                        support=support,
                        source={
                            "learner": "tree",
                            "target_predicate_id": target.predicate_id,
                            "target_display": target.display,
                            "purity": purity,
                        },
                    ))
                    return
                feature_index = int(tree.feature[node_id])
                # sklearn 对 0/1 特征的树分裂通常是 <= 0.5 走左，> 0.5 走右。
                # 因此左分支表示该谓词为 False，右分支表示该谓词为 True。
                walk(left, [*conditions, (feature_index, False)])
                walk(right, [*conditions, (feature_index, True)])

            walk(0, [])
        self.last_fit_metadata = {
            "rule_count": len(rules),
            "predicate_count": len(predicates),
        }
        return rules


def build_path_formula(
    conditions: list[tuple[int, bool]],
    predicates: list[GroundedPredicate],
    feature_indices: list[int],
) -> Formula | None:
    """把树路径条件恢复成合取前提公式。

    决策树内部只知道“第几个特征为 0/1”，
    这里需要把这些特征下标重新映射回原始谓词公式。

    示例：
    - 条件 `(3, True)`  -> 第 3 个特征对应谓词本身；
    - 条件 `(5, False)` -> 第 5 个特征对应谓词的 NOT。

    多个路径条件会用 BoolAnd 合成一个 premise。
    """
    literals: list[Formula] = []
    for local_index, positive in conditions:
        predicate = predicates[feature_indices[local_index]].formula
        literals.append(predicate if positive else BoolNot(predicate))
    if not literals:
        return None
    if len(literals) == 1:
        return literals[0]
    return BoolAnd(tuple(literals))
