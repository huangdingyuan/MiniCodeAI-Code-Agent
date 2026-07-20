"""
RAGAS 评测脚本
计算 RAG 系统的 Faithfulness、Answer Relevancy、Context Relevancy

使用方式:
    python -m backend.evaluation.ragas_eval --test-file tests/test_dataset.json
    或直接运行 python ragas_eval.py（在 backend 目录下）

测试数据集格式（JSON）:
[
    {
        "question": "什么是 RAG?",
        "ground_truth": "RAG 是检索增强生成...",
        "ground_truth_contexts": ["RAG（Retrieval-Augmented Generation）..."]
    },
    ...
]
"""
import asyncio
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加 backend 目录到 Python 路径
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from services.agent_service import agent_service
from services.vector_store import vector_store


# 默认测试数据集
DEFAULT_TEST_DATASET = [
    {
        "question": "什么是 RAG？",
        "ground_truth": "RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合信息检索和生成模型的方法，通过从外部知识库检索相关文档来增强 LLM 的回答能力。",
        "ground_truth_contexts": [
            "RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合信息检索和生成模型的方法。"
        ],
    },
    {
        "question": "什么是 Agent？",
        "ground_truth": "Agent（智能体）是能够自主规划、调用工具完成任务的程序，基于 LLM 实现。",
        "ground_truth_contexts": [
            "Agent 智能体，能够自主规划、调用工具完成任务的程序。"
        ],
    },
    {
        "question": "BM25 算法的作用是什么？",
        "ground_truth": "BM25 是一种经典的文本相关性评分算法，用于全文检索，基于词频和逆文档频率计算文档与查询的相关度。",
        "ground_truth_contexts": [
            "BM25 一种经典的文本相关性评分算法，用于全文检索。"
        ],
    },
]


async def generate_rag_response(question: str) -> Dict[str, Any]:
    """对单个问题运行 RAG 流程，返回回答和上下文"""
    # 1. 检索文档
    retrieved_docs = vector_store.search(query=question, n_results=5)
    contexts = [doc.get("content", "") for doc in retrieved_docs if doc.get("content")]

    # 2. 生成回答（非流式）
    response = await agent_service.chat(message=question, chat_history=[])

    return {
        "question": question,
        "answer": response,
        "contexts": contexts,
    }


async def evaluate_dataset(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """使用 RAGAS 评测数据集"""
    print(f"\n{'=' * 60}")
    print(f"开始评测，共 {len(dataset)} 个问题")
    print(f"{'=' * 60}\n")

    # 1. 生成 RAG 响应
    rag_results = []
    for i, item in enumerate(dataset, 1):
        print(f"[{i}/{len(dataset)}] 正在生成回答: {item['question'][:50]}...")
        result = await generate_rag_response(item["question"])
        # 合并 ground_truth
        result["ground_truth"] = item["ground_truth"]
        result["ground_truth_contexts"] = item.get("ground_truth_contexts", [])
        rag_results.append(result)
        print(f"    回答长度: {len(result['answer'])} 字符")
        print(f"    检索到 {len(result['contexts'])} 个文档片段\n")

    # 2. 准备 RAGAS 数据集
    try:
        from datasets import Dataset
        import pandas as pd
    except ImportError:
        print("错误：需要安装 datasets 和 pandas 库")
        print("运行: pip install datasets pandas")
        return {"error": "missing dependencies", "results": rag_results}

    # 构造 RAGAS 期望的数据格式
    eval_data = {
        "question": [r["question"] for r in rag_results],
        "answer": [r["answer"] for r in rag_results],
        "contexts": [r["contexts"] for r in rag_results],
        "ground_truth": [r["ground_truth"] for r in rag_results],
        "ground_truth_contexts": [r["ground_truth_contexts"] for r in rag_results],
    }

    eval_dataset = Dataset.from_dict(eval_data)
    print(f"\n构造评测数据集完成，共 {len(eval_dataset)} 条样本")
    print(f"{'=' * 60}\n")

    # 3. 运行 RAGAS 评测
    try:
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_relevancy,
            context_precision,
            context_recall,
        )
    except ImportError:
        print("错误：需要安装 ragas 库")
        print("运行: pip install ragas")
        return {"error": "ragas not installed", "results": rag_results}

    try:
        print("正在运行 RAGAS 评测（这可能需要一些时间）...\n")
        result = evaluate(
            eval_dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_relevancy,
                context_precision,
                context_recall,
            ],
        )
        result_df = result.to_pandas()
        print(f"\n{'=' * 60}")
        print("RAGAS 评测结果：")
        print(f"{'=' * 60}\n")
        print(result_df.to_string(index=False))

        # 计算平均值
        print(f"\n{'=' * 60}")
        print("指标平均值：")
        print(f"{'=' * 60}")
        avg_metrics = {}
        for col in result_df.columns:
            if col not in ["question", "answer", "contexts", "ground_truth", "ground_truth_contexts"]:
                avg_val = result_df[col].mean()
                avg_metrics[col] = float(avg_val)
                print(f"  {col}: {avg_val:.4f}")

        # 保存结果
        output_path = BACKEND_DIR / "evaluation" / "ragas_results.json"
        os.makedirs(output_path.parent, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "metrics": avg_metrics,
                "details": rag_results,
                "raw_results": result_df.to_dict(orient="records"),
            }, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n结果已保存到: {output_path}")

        return {"metrics": avg_metrics, "results": rag_results}

    except Exception as e:
        print(f"RAGAS 评测失败: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "results": rag_results}


async def main_async(args):
    """异步主函数"""
    # 加载测试数据集
    dataset = DEFAULT_TEST_DATASET
    if args.test_file:
        if not os.path.exists(args.test_file):
            print(f"错误：测试文件不存在: {args.test_file}")
            return
        with open(args.test_file, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        print(f"已加载测试数据集: {args.test_file} ({len(dataset)} 条)")

    # 运行评测
    result = await evaluate_dataset(dataset)

    # 返回退出码
    if "error" in result:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="RAGAS RAG 系统评测")
    parser.add_argument(
        "--test-file",
        type=str,
        default=None,
        help="测试数据集 JSON 文件路径（不指定则使用内置数据集）",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
