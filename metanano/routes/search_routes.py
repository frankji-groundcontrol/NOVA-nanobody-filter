"""
References / 参考:
    - docs/en/README.md: Section 3 - Search Routes
    - docs/cn/README.md: 第3节 - 搜索路由
    - metanano/services/search_service.py: SearchService

File / 文件:
    - metanano/routes/search_routes.py

Overview / 概述:
    API routes for async sequence search submission, polling, and indexing.
    用于异步序列搜索提交、轮询与建索引的 API 路由。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - metanano/app.py
"""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from metanano.config import Config
from metanano.services.search_service import SearchService
from metanano.utils.kmer import generate_kmers

router = APIRouter(prefix="/search", tags=["Search"])

# Global service instance
# 全局服务实例
_config = Config()
_search_service = SearchService(_config.search)

_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


def _serialize_result(value: Any) -> Any:
    """
    Convert dataclass-heavy result objects to JSON-safe structures.
    将包含 dataclass 的结果转换为 JSON 安全结构。

    Args:
        value (Any): Input object that may contain dataclasses, lists, or dicts.
            可能包含 dataclass、列表或字典的输入对象。

    Returns:
        Any: JSON-serializable structure.
            可 JSON 序列化的数据结构。
    """
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize_result(asdict(value))
    if isinstance(value, list):
        return [_serialize_result(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_result(v) for k, v in value.items()}
    return value


class SearchRequest(BaseModel):
    """
    Request model for async search submission.
    异步搜索提交请求模型。
    """

    sequences: List[str] = Field(
        ...,
        min_length=1,
        description="Query sequences to search. / 待搜索的查询序列列表。",
    )
    include_alignment: bool = Field(
        default=False,
        description="Whether to return aligned strings. / 是否返回对齐字符串。",
    )
    coarse_min_shared: Optional[int] = Field(
        default=None,
        description="Override coarse min shared k-mers. / 覆盖粗过滤最小共享 k-mer。",
    )
    coarse_jaccard: Optional[float] = Field(
        default=None,
        description="Override coarse Jaccard threshold. / 覆盖粗过滤 Jaccard 阈值。",
    )

    @field_validator("sequences")
    @classmethod
    def validate_sequences(cls, values: List[str]) -> List[str]:
        """
        Validate query sequences and normalize to uppercase.
        验证查询序列并规范为大写。

        Args:
            values (List[str]): Raw query sequence list.
                原始查询序列列表。

        Returns:
            List[str]: Normalized uppercase sequence list.
                规范化后的大写序列列表。

        Raises:
            ValueError: If a sequence violates character or length constraints.
                当序列字符或长度不满足约束时抛出。
        """
        normalized: List[str] = []
        for idx, seq in enumerate(values):
            candidate = re.sub(r"\s+", "", seq.strip().upper())
            if len(candidate) < 10 or len(candidate) > 500:
                raise ValueError(
                    f"Sequence {idx}: length must be in [10, 500]. / "
                    f"序列 {idx}：长度必须在 [10, 500] 内。"
                )
            invalid = set(candidate) - _AMINO_ACIDS
            if invalid:
                raise ValueError(
                    f"Sequence {idx}: invalid amino acids {sorted(invalid)}. / "
                    f"序列 {idx}：无效氨基酸字符 {sorted(invalid)}。"
                )
            normalized.append(candidate)
        return normalized


class SearchJobResponse(BaseModel):
    """
    Response model for search job submission.
    搜索任务提交响应模型。
    """

    job_id: str = Field(..., description="Search job ID. / 搜索任务 ID。")


class SearchStatusResponse(BaseModel):
    """
    Response model for search job status.
    搜索任务状态响应模型。
    """

    job_id: str
    status: str
    created_at: float
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class IndexSequenceRequest(BaseModel):
    """
    Request model for adding one sequence into search index.
    单条序列入索引请求模型。
    """

    id: str = Field(..., min_length=1, description="Sequence ID. / 序列 ID。")
    sequence: str = Field(..., min_length=10, max_length=500)
    cdrs: Optional[Dict[str, str]] = None

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        """
        Validate and normalize an indexed sequence.
        验证并规范化待索引序列。

        Args:
            value (str): Raw indexed sequence.
                原始待索引序列。

        Returns:
            str: Normalized uppercase sequence.
                规范化后的大写序列。

        Raises:
            ValueError: If invalid amino-acid characters are present.
                当存在无效氨基酸字符时抛出。
        """
        candidate = re.sub(r"\s+", "", value.strip().upper())
        invalid = set(candidate) - _AMINO_ACIDS
        if invalid:
            raise ValueError(
                f"Invalid amino acids {sorted(invalid)}. / 无效氨基酸字符 {sorted(invalid)}。"
            )
        return candidate


class IndexStatsResponse(BaseModel):
    """
    Response model for current search index stats.
    当前搜索索引统计响应模型。
    """

    total_sequences: int


@router.post(
    "",
    response_model=SearchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Search Job / 提交搜索任务",
)
async def submit_search(request: SearchRequest) -> SearchJobResponse:
    """
    Submit an asynchronous search job.
    提交异步搜索任务。

    Args:
        request (SearchRequest): Search submission payload.
            搜索提交请求体。

    Returns:
        SearchJobResponse: Created job identifier.
            创建的任务标识符。

    Raises:
        HTTPException: If backend submission fails.
            当后端提交失败时抛出。
    """
    try:
        job_id = await _search_service.submit_search(
            queries=request.sequences,
            include_alignment=request.include_alignment,
            coarse_min_shared=request.coarse_min_shared,
            coarse_jaccard=request.coarse_jaccard,
        )
        return SearchJobResponse(job_id=job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit search: {exc} / 提交搜索失败：{exc}",
        )


@router.get(
    "/{job_id}",
    response_model=SearchStatusResponse,
    summary="Get Search Job Status / 获取搜索任务状态",
)
async def get_search_status(job_id: str) -> SearchStatusResponse:
    """
    Get one search job status and optional result payload.
    获取单个搜索任务状态及可选结果载荷。

    Args:
        job_id (str): Search job identifier.
            搜索任务标识符。

    Returns:
        SearchStatusResponse: Current job status snapshot.
            当前任务状态快照。

    Raises:
        HTTPException: If the job does not exist.
            当任务不存在时抛出。
    """
    job = await _search_service.get_job_status(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id} / 任务不存在：{job_id}",
        )

    return SearchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        created_at=job.created_at,
        completed_at=job.completed_at,
        result=_serialize_result(job.result),
        error=job.error,
    )


@router.post(
    "/index",
    status_code=status.HTTP_201_CREATED,
    summary="Index One Sequence / 索引单条序列",
)
async def index_sequence(request: IndexSequenceRequest) -> Dict[str, str]:
    """
    Add one sequence into in-memory search index.
    将单条序列加入内存搜索索引。

    Args:
        request (IndexSequenceRequest): Sequence indexing payload.
            序列索引请求体。

    Returns:
        Dict[str, str]: Index confirmation payload.
            索引确认响应。

    Raises:
        HTTPException: If indexing fails.
            当索引失败时抛出。
    """
    try:
        k = _config.search.k
        kmers = generate_kmers(request.sequence, k=k)
        _search_service.index_sequence(
            seq_id=request.id,
            sequence=request.sequence,
            cdrs=request.cdrs,
            kmers=kmers,
        )
        return {"status": "indexed", "id": request.id}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index sequence: {exc} / 索引序列失败：{exc}",
        )


@router.get(
    "/index/stats",
    response_model=IndexStatsResponse,
    summary="Get Index Stats / 获取索引统计",
)
async def get_index_stats() -> IndexStatsResponse:
    """
    Return current in-memory index size.
    返回当前内存索引大小。

    Returns:
        IndexStatsResponse: Count of indexed sequences.
            已索引序列数量。
    """
    return IndexStatsResponse(total_sequences=_search_service._index_manager.size())
