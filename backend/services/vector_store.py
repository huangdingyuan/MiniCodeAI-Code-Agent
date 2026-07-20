"""
向量存储服务（嵌入式本地模式）
使用 ChromaDB 持久化本地存储，无需启动独立服务
支持混合检索（向量 + BM25）+ Rerank 重排序提升精度
"""
import os
import logging
import hashlib
import math
from typing import List, Dict, Any, Optional

import chromadb
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class SimpleEmbeddingFunction:
    """
    简单的 Embedding 函数（基于哈希）
    用于开发调试，无需下载模型
    注意：生产环境建议替换为 sentence-transformers 或其他专业模型
    """
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """生成简单的哈希向量（384维）"""
        embeddings = []
        for text in input:
            # 使用 MD5 生成 32 字节哈希
            hash_bytes = hashlib.md5(text.encode('utf-8')).digest()
            # 扩展为 384 维向量（重复 12 次）
            vector = []
            for i in range(384):
                byte_idx = i % len(hash_bytes)
                vector.append(float(hash_bytes[byte_idx]) / 255.0)
            # 归一化
            norm = sum(v * v for v in vector) ** 0.5
            if norm > 0:
                vector = [v / norm for v in vector]
            embeddings.append(vector)
        return embeddings


class SemanticTextSplitter:
    """
    语义感知文本分割器
    按段落、标题、代码块等语义边界分块，避免截断完整内容
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # 语义分隔符优先级：双换行 > 标题 > 单换行 > 句号 > 空格
        self.separators = [
            "\n\n\n",    # 多段落间隔
            "\n\n",      # 段落间隔
            "\n=== ",    # 表格/区块标记
            "\n# ",      # Markdown 标题
            "\n## ",
            "\n### ",
            "\n",        # 换行
            "。", ".", "！", "!", "？", "?",  # 句子结束
            "；", ";", "，", ",",  # 分句
            " ",         # 单词间隔
            "",          # 字符级（最后手段）
        ]

    def split_text(self, text: str) -> List[str]:
        """按语义边界分割文本"""
        if not text or not text.strip():
            return []

        # 先按最大分隔符分割成段落
        paragraphs = self._split_by_separators(text)

        # 合并短段落，拆分长段落
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前块 + 新段落不超过限制，合并
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # 保存当前块
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果新段落本身超长，需要进一步拆分
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_text(para)
                    # 保留重叠
                    for i, sc in enumerate(sub_chunks):
                        if i > 0 and chunks:
                            # 与前一个 chunk 保留重叠
                            prev = chunks[-1] if sub_chunks.index(sc) == 0 else sub_chunks[i-1]
                            overlap_text = prev[-self.chunk_overlap:] if len(prev) > self.chunk_overlap else prev
                            sc = overlap_text + "\n" + sc
                        chunks.append(sc)
                else:
                    current_chunk = para

        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        # 添加重叠信息到相邻块
        if self.chunk_overlap > 0 and len(chunks) > 1:
            for i in range(1, len(chunks)):
                prev_tail = chunks[i-1][-self.chunk_overlap:]
                if prev_tail not in chunks[i]:
                    chunks[i] = prev_tail + "\n" + chunks[i]

        return [c.strip() for c in chunks if c.strip()]

    def _split_by_separators(self, text: str) -> List[str]:
        """按优先级分隔符递归分割"""
        for sep in self.separators:
            if not sep:
                return list(text)
            if sep in text:
                parts = text.split(sep)
                # 如果分割后每段都不超过 chunk_size，返回
                if all(len(p.strip()) <= self.chunk_size for p in parts if p.strip()):
                    return [p.strip() for p in parts if p.strip()]
                # 否则对超长部分继续用下一个分隔符
                result = []
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    if len(part) > self.chunk_size:
                        # 用下一个分隔符继续分割
                        next_seps = self.separators[self.separators.index(sep) + 1:]
                        sub_text = part
                        for next_sep in next_seps:
                            if not next_sep:
                                result.extend(self._split_fixed_size(sub_text))
                                sub_text = None
                                break
                            if next_sep in sub_text:
                                sub_parts = sub_text.split(next_sep)
                                if all(len(p.strip()) <= self.chunk_size for p in sub_parts if p.strip()):
                                    result.extend(p.strip() for p in sub_parts if p.strip())
                                    sub_text = None
                                    break
                        if sub_text:
                            result.extend(self._split_fixed_size(sub_text))
                    else:
                        result.append(part)
                return result
        return self._split_fixed_size(text)

    def _split_long_text(self, text: str) -> List[str]:
        """拆分超长文本"""
        return self._split_fixed_size(text)

    def _split_fixed_size(self, text: str) -> List[str]:
        """按固定大小分割（最后手段）"""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk.strip():
                chunks.append(chunk.strip())
        return chunks


class VectorStore:
    """向量存储服务（嵌入式本地模式）"""

    def __init__(self):
        """初始化 ChromaDB 客户端（嵌入式本地模式）"""
        persist_directory = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
        os.makedirs(persist_directory, exist_ok=True)

        # 嵌入式本地模式：数据持久化到本地磁盘
        self.client = chromadb.PersistentClient(path=persist_directory)

        # 使用简单的哈希 Embedding 函数（无需下载模型）
        self.embedding_function = SimpleEmbeddingFunction()

        # 语义感知文本分割器
        self.text_splitter = SemanticTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
        )

        # BM25 索引缓存（内存中）
        self._bm25_indices: Dict[str, BM25Okapi] = {}
        self._bm25_corpus: Dict[str, List[str]] = {}

        # 启动时从持久化存储重建 BM25 索引
        self._rebuild_bm25_index()

    def _rebuild_bm25_index(self):
        """从 ChromaDB 持久化存储重建 BM25 索引（解决重启后 BM25 索引丢失问题）"""
        try:
            collection = self.get_or_create_collection("documents")
            results = collection.get(include=["documents", "metadatas"])
            if not results or not results.get('ids'):
                logger.info("BM25 重建：向量库为空")
                return

            # 按 doc_id 分组重建
            doc_chunks: Dict[str, List[tuple]] = {}
            for chunk_id, doc, meta in zip(
                results['ids'],
                results['documents'],
                results['metadatas']
            ):
                doc_id = meta.get("doc_id", "")
                chunk_index = meta.get("chunk_index", 0)
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = []
                doc_chunks[doc_id].append((chunk_index, doc))

            # 按 chunk_index 排序后重建 BM25 索引
            for doc_id, chunks in doc_chunks.items():
                chunks.sort(key=lambda x: x[0])
                chunk_texts = [c[1] for c in chunks]
                self._update_bm25_index(doc_id, chunk_texts, "documents")

            logger.info(
                f"BM25 索引重建完成：{len(doc_chunks)} 个文档，"
                f"共 {len(results['ids'])} 个文本块"
            )
        except Exception as e:
            logger.error(f"BM25 索引重建失败: {e}")

    def get_or_create_collection(self, collection_name: str = "documents"):
        """获取或创建集合"""
        return self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        collection_name: str = "documents"
    ) -> List[str]:
        """
        添加文档到向量库

        Args:
            doc_id: 文档 ID
            text: 文档文本内容
            metadata: 元数据
            collection_name: 集合名称

        Returns:
            chunk_ids: 文本块的 ID 列表
        """
        collection = self.get_or_create_collection(collection_name)

        # 语义分割文本
        chunks = self.text_splitter.split_text(text)

        if not chunks:
            logger.warning(f"文档 {doc_id} 分割后无内容")
            return []

        # 为每个 chunk 生成 ID
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]

        # 准备元数据
        chunk_metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_meta = {
                "doc_id": str(doc_id),
                "chunk_index": i,
                "chunk_length": len(chunk),
            }
            if metadata:
                for k, v in metadata.items():
                    chunk_meta[k] = str(v) if not isinstance(v, (str, int, float, bool)) else v

            # FR-11 解析页码标记：识别文本中的 [[PAGE:N]] 标记
            # 由 PDF/DOCX 解析器写入，用于精确标注引用页码
            page_num = self._extract_page_number(chunk)
            if page_num is not None:
                chunk_meta["page"] = page_num
                # 清理 chunk 中的页码标记（不展示给用户）
                chunk = self._strip_page_markers(chunk)
                chunks[i] = chunk

            chunk_metadatas.append(chunk_meta)

        # 添加到向量库
        collection.add(
            ids=chunk_ids,
            documents=chunks,
            metadatas=chunk_metadatas
        )

        # 更新 BM25 索引
        self._update_bm25_index(doc_id, chunks, collection_name)

        logger.info(f"文档 {doc_id} 已添加到向量库，共 {len(chunks)} 个文本块")
        return chunk_ids

    def _update_bm25_index(self, doc_id: str, chunks: List[str], collection_name: str):
        """更新 BM25 索引"""
        key = f"{collection_name}:{doc_id}"
        # 分词（简单中文分词：按字符 + 常见词）
        tokenized = [self._tokenize(chunk) for chunk in chunks]
        self._bm25_indices[key] = BM25Okapi(tokenized)
        self._bm25_corpus[key] = chunks

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """简单分词：中文按字，英文按词"""
        import re
        # 英文单词
        words = re.findall(r'[a-zA-Z0-9_]+', text)
        # 中文字符（提取所有汉字）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        return words + chinese_chars

    @staticmethod
    def _extract_page_number(text: str) -> Optional[int]:
        """FR-11 从文本中提取页码标记 [[PAGE:N]]
        返回第一个找到的页码，找不到返回 None
        """
        import re
        match = re.search(r'\[\[PAGE:(\d+)\]\]', text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _strip_page_markers(text: str) -> str:
        """FR-11 清理文本中的页码标记 [[PAGE:N]]"""
        import re
        return re.sub(r'\[\[PAGE:\d+\]\]\s*', '', text)

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_doc_id: Optional[str] = None,
        collection_name: str = "documents"
    ) -> List[Dict[str, Any]]:
        """
        混合检索：向量检索 + BM25 关键词检索，融合排序

        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_doc_id: 按文档 ID 过滤
            collection_name: 集合名称

        Returns:
            检索结果列表（按融合分数排序）
        """
        collection = self.get_or_create_collection(collection_name)

        # 1. 向量检索
        where_filter = None
        if filter_doc_id:
            where_filter = {"doc_id": str(filter_doc_id)}

        vector_results = collection.query(
            query_texts=[query],
            n_results=min(n_results * 2, 20),  # 多取一些用于融合
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        # 2. BM25 关键词检索
        bm25_scores = self._bm25_search(query, filter_doc_id, collection_name)

        # 3. 融合排序
        return self._hybrid_rank(vector_results, bm25_scores, n_results)

    def _bm25_search(
        self,
        query: str,
        filter_doc_id: Optional[str],
        collection_name: str
    ) -> Dict[str, float]:
        """BM25 关键词检索（分数归一化到 0-1 范围）"""
        query_tokens = self._tokenize(query)
        raw_scores = {}

        if filter_doc_id:
            key = f"{collection_name}:{filter_doc_id}"
            if key in self._bm25_indices:
                bm25 = self._bm25_indices[key]
                doc_scores = bm25.get_scores(query_tokens)
                for i, score in enumerate(doc_scores):
                    if score > 0:
                        chunk_id = f"{filter_doc_id}_chunk_{i}"
                        raw_scores[chunk_id] = float(score)
        else:
            # 搜索所有文档
            for key, bm25 in self._bm25_indices.items():
                if not key.startswith(collection_name):
                    continue
                doc_scores = bm25.get_scores(query_tokens)
                doc_id = key.split(":", 1)[1]
                for i, score in enumerate(doc_scores):
                    if score > 0:
                        chunk_id = f"{doc_id}_chunk_{i}"
                        raw_scores[chunk_id] = float(score)

        # 归一化到 0-1 范围（除以最大值，避免 BM25 原始分数过大）
        if not raw_scores:
            return {}
        max_score = max(raw_scores.values())
        if max_score <= 0:
            return {}
        return {k: v / max_score for k, v in raw_scores.items()}

    def _hybrid_rank(
        self,
        vector_results: Dict,
        bm25_scores: Dict[str, float],
        n_results: int
    ) -> List[Dict[str, Any]]:
        """融合向量检索和 BM25 结果"""
        # 归一化函数
        def normalize(scores: List[float]) -> List[float]:
            if not scores:
                return []
            min_s, max_s = min(scores), max(scores)
            if max_s == min_s:
                return [0.5] * len(scores)
            return [(s - min_s) / (max_s - min_s) for s in scores]

        # 收集所有候选
        candidates = {}

        # 向量结果
        if vector_results and vector_results.get('documents') and vector_results['documents'][0]:
            distances = vector_results['distances'][0]
            min_d, max_d = min(distances), max(distances)
            for i, (doc, meta, dist) in enumerate(
                zip(vector_results['documents'][0], vector_results['metadatas'][0], distances)
            ):
                chunk_id = vector_results['ids'][0][i]
                # 距离转相似度（归一化）
                vec_score = 1 - ((dist - min_d) / (max_d - min_d)) if max_d > min_d else 0.5
                candidates[chunk_id] = {
                    "chunk_id": chunk_id,
                    "content": doc,
                    "metadata": meta,
                    "vector_score": vec_score,
                    "bm25_score": bm25_scores.get(chunk_id, 0.0),
                }

        # BM25 结果（可能包含向量检索未覆盖的 chunk）
        for chunk_id, score in bm25_scores.items():
            if chunk_id not in candidates:
                # 从 corpus 中获取内容
                for key, corpus in self._bm25_corpus.items():
                    doc_id = key.split(":", 1)[1]
                    prefix = f"{doc_id}_chunk_"
                    if chunk_id.startswith(prefix):
                        idx = int(chunk_id[len(prefix):])
                        if idx < len(corpus):
                            candidates[chunk_id] = {
                                "chunk_id": chunk_id,
                                "content": corpus[idx],
                                "metadata": {"doc_id": doc_id, "chunk_index": idx},
                                "vector_score": 0.0,
                                "bm25_score": score,
                            }
                        break

        if not candidates:
            return []

        # 融合分数：向量 0.6 + BM25 0.4（两者都已在 0-1 范围）
        for c in candidates.values():
            c["hybrid_score"] = min(1.0, 0.6 * c["vector_score"] + 0.4 * c["bm25_score"])

        # 按融合分数排序
        ranked = sorted(candidates.values(), key=lambda x: x["hybrid_score"], reverse=True)

        # 直接使用 hybrid_score 作为 relevance_score（已限制在 0-1 范围）
        # 这样 relevance_score 反映真实相关度，可用于绝对阈值判断
        for r in ranked[:n_results]:
            r["relevance_score"] = r["hybrid_score"]

        return ranked[:n_results]

    def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        FR-9 Rerank 重排序（增强版）：
        1. 词重叠相似度（Jaccard）
        2. 查询覆盖率（query 中有多少词出现在文档中）
        3. 文档长度归一化重叠度
        4. TF-IDF 加权（查询词在文档中的重要性）

        Args:
            query: 查询文本
            candidates: 待重排序的候选结果列表
            top_n: 返回前 N 个结果

        Returns:
            重排序后的结果列表（所有分数严格限制在 0-1 范围）
        """
        if not candidates:
            return []

        query_tokens_list = self._tokenize(query)
        query_tokens = set(query_tokens_list)
        # 查询词频（用于 TF-IDF）
        query_tf: Dict[str, int] = {}
        for t in query_tokens_list:
            query_tf[t] = query_tf.get(t, 0) + 1
        query_total = len(query_tokens_list) or 1

        # 计算每个候选文档的 IDF（基于候选集）
        N = len(candidates)
        doc_freq: Dict[str, int] = {}
        for c in candidates:
            seen = set(self._tokenize(c.get("content", "")))
            for tok in seen:
                doc_freq[tok] = doc_freq.get(tok, 0) + 1

        reranked = []
        for candidate in candidates:
            content = candidate.get("content", "")
            content_tokens_list = self._tokenize(content)
            content_tokens = set(content_tokens_list)

            # 1. 词重叠相似度（Jaccard，范围 0-1）
            if query_tokens or content_tokens:
                jaccard = len(query_tokens & content_tokens) / len(query_tokens | content_tokens)
            else:
                jaccard = 0.0

            # 2. 查询覆盖率：query 中有多少比例的词出现在文档中（范围 0-1）
            if query_tokens:
                coverage = len(query_tokens & content_tokens) / len(query_tokens)
            else:
                coverage = 0.0

            # 3. 文本长度归一化的重叠度（限制在 0-1 范围）
            if len(content_tokens) > 0:
                overlap_ratio = min(1.0, len(query_tokens & content_tokens) / math.sqrt(len(content_tokens)))
            else:
                overlap_ratio = 0.0

            # 4. TF-IDF 加权分数
            tfidf_score = 0.0
            content_tf: Dict[str, int] = {}
            for t in content_tokens_list:
                content_tf[t] = content_tf.get(t, 0) + 1
            content_total = len(content_tokens_list) or 1
            for q_tok, q_count in query_tf.items():
                if q_tok in content_tf:
                    tf = content_tf[q_tok] / content_total
                    df = doc_freq.get(q_tok, 0)
                    idf = math.log((N + 1) / (df + 1)) if N > 0 and df > 0 else 1.0
                    tfidf_score += tf * idf * (q_count / query_total)
            # 归一化到 0-1
            tfidf_score = min(1.0, tfidf_score)

            # 综合 Rerank 分数：
            # - coverage（覆盖率）权重最高，反映查询与文档的强相关性
            # - tfidf（TF-IDF）反映关键词匹配质量
            # - jaccard 和 overlap 是辅助指标
            rerank_score = (
                0.35 * coverage
                + 0.30 * tfidf_score
                + 0.20 * jaccard
                + 0.15 * overlap_ratio
            )
            rerank_score = min(1.0, max(0.0, rerank_score))

            # 结合原有的混合分数（hybrid_score 已在 0-1 范围）
            hybrid_score = min(1.0, candidate.get("hybrid_score", 0.0))
            final_score = 0.6 * hybrid_score + 0.4 * rerank_score
            final_score = min(1.0, max(0.0, final_score))

            reranked.append({
                **candidate,
                "rerank_score": rerank_score,
                "coverage": coverage,
                "tfidf_score": tfidf_score,
                "final_score": final_score,
            })

        # 按最终分数排序
        reranked.sort(key=lambda x: x["final_score"], reverse=True)

        # 直接使用 final_score 作为 relevance_score（严格限制在 0-1 范围）
        for r in reranked[:top_n]:
            r["relevance_score"] = min(1.0, max(0.0, r["final_score"]))

        return reranked[:top_n]

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_doc_id: Optional[str] = None,
        collection_name: str = "documents",
        use_rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """
        混合检索：向量检索 + BM25 关键词检索，融合排序 + Rerank 重排序

        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_doc_id: 按文档 ID 过滤
            collection_name: 集合名称
            use_rerank: 是否启用 Rerank 重排序

        Returns:
            检索结果列表（按融合分数排序，可选 Rerank）
        """
        collection = self.get_or_create_collection(collection_name)

        # 1. 向量检索
        where_filter = None
        if filter_doc_id:
            where_filter = {"doc_id": str(filter_doc_id)}

        # 多取一些用于后续重排序
        fetch_n = min(n_results * 3, 30)
        vector_results = collection.query(
            query_texts=[query],
            n_results=fetch_n,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        # 2. BM25 关键词检索
        bm25_scores = self._bm25_search(query, filter_doc_id, collection_name)

        # 3. 融合排序（取较多候选用于 Rerank）
        hybrid_results = self._hybrid_rank(vector_results, bm25_scores, fetch_n)

        # 4. Rerank 重排序
        if use_rerank and hybrid_results:
            return self._rerank(query, hybrid_results, n_results)

        return hybrid_results[:n_results]

    def delete_document(self, doc_id: str, collection_name: str = "documents"):
        """删除文档的所有文本块"""
        collection = self.get_or_create_collection(collection_name)

        try:
            results = collection.get(
                where={"doc_id": str(doc_id)},
                include=[]
            )
            if results and results['ids']:
                collection.delete(ids=results['ids'])
                logger.info(f"文档 {doc_id} 已从向量库删除，共删除 {len(results['ids'])} 个文本块")
        except Exception as e:
            logger.error(f"删除文档 {doc_id} 失败: {e}")

        # 清理 BM25 索引
        key = f"{collection_name}:{doc_id}"
        self._bm25_indices.pop(key, None)
        self._bm25_corpus.pop(key, None)

    def get_document_chunks(self, doc_id: str, collection_name: str = "documents") -> List[Dict[str, Any]]:
        """获取文档的所有文本块"""
        collection = self.get_or_create_collection(collection_name)
        try:
            results = collection.get(
                where={"doc_id": str(doc_id)},
                include=["documents", "metadatas"]
            )
            chunks = []
            if results and results['documents']:
                for doc, meta in zip(results['documents'], results['metadatas']):
                    chunks.append({"content": doc, "metadata": meta})
            return chunks
        except Exception as e:
            logger.error(f"获取文档 {doc_id} 文本块失败: {e}")
            return []

    def get_collection_stats(self, collection_name: str = "documents") -> Dict[str, Any]:
        """获取集合统计信息"""
        collection = self.get_or_create_collection(collection_name)
        count = collection.count()
        return {
            "total_chunks": count,
            "total_documents": len(self._bm25_indices),
            "bm25_indices": len(self._bm25_indices),
        }


# 全局单例
vector_store = VectorStore()
