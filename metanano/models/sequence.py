"""
References / 参考:
    - docs/en/README.md: Section 3 - Routes (API Definitions)
    - docs/cn/README.md: 第3节 - 路由（API定义）

File / 文件:
    - metanano/models/sequence.py

Overview / 概述:
    Pydantic models for nanobody sequence data.
    纳米抗体序列数据的 Pydantic 模型。

Consumers / 调用方:
    - metanano/models/__init__.py
    - metanano/routes/submission_routes.py
    - metanano/routes/validation_routes.py
"""

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# Valid amino acid characters
# 有效的氨基酸字符
AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


class Sequence(BaseModel):
    """
    Model for a single nanobody sequence.
    单个纳米抗体序列的模型。

    Example / 示例:
        >>> seq = Sequence(sequence="EVQLVESGGGLVQPGG...")
        >>> print(seq.sequence)

    Consumers / 调用方:
        - metanano/routes/validation_routes.py
    """

    sequence: str = Field(
        ...,
        min_length=50,
        max_length=200,
        description="Amino acid sequence of the nanobody (VHH). "
        "Must be 50-200 characters, uppercase letters only. / "
        "纳米抗体（VHH）的氨基酸序列。必须为50-200个字符，仅大写字母。",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: str) -> str:
        """
        Validate and normalize the sequence.
        验证并规范化序列。

        Args / 参数:
            v (str): Raw sequence input.
                原始序列输入。

        Returns / 返回:
            str: Normalized uppercase sequence.
                规范化的大写序列。

        Raises / 异常:
            ValueError: If sequence contains invalid characters.
                如果序列包含无效字符。
        """
        # Normalize: uppercase and remove whitespace
        # 规范化：转大写并移除空白
        v = v.upper().strip()
        v = re.sub(r"\s+", "", v)

        # Check for valid amino acids
        # 检查有效的氨基酸
        invalid_chars = set(v) - AMINO_ACIDS
        if invalid_chars:
            raise ValueError(
                f"Invalid amino acid characters: {sorted(invalid_chars)}. / "
                f"无效的氨基酸字符：{sorted(invalid_chars)}。"
            )

        return v

    class Config:
        """Pydantic configuration. / Pydantic 配置。"""

        json_schema_extra = {
            "example": {
                "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS"
            }
        }


class SequenceSubmission(BaseModel):
    """
    Model for sequence submission request.
    序列提交请求的模型。

    Consumers / 调用方:
        - metanano/routes/submission_routes.py
    """

    sequence: str = Field(
        ...,
        min_length=50,
        max_length=200,
        description="Amino acid sequence of the nanobody. / "
        "纳米抗体的氨基酸序列。",
    )
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier of the submitting user. / "
        "提交用户的唯一标识符。",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: str) -> str:
        """Validate sequence (same as Sequence model). / 验证序列。"""
        v = v.upper().strip()
        v = re.sub(r"\s+", "", v)
        invalid_chars = set(v) - AMINO_ACIDS
        if invalid_chars:
            raise ValueError(
                f"Invalid amino acid characters: {sorted(invalid_chars)}. / "
                f"无效的氨基酸字符：{sorted(invalid_chars)}。"
            )
        return v

    class Config:
        """Pydantic configuration. / Pydantic 配置。"""

        json_schema_extra = {
            "example": {
                "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS",
                "user_id": "user_12345",
            }
        }


class SequenceBatch(BaseModel):
    """
    Model for batch sequence submission.
    批量序列提交的模型。

    Consumers / 调用方:
        - metanano/routes/submission_routes.py (batch endpoint)
    """

    sequences: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of nanobody sequences to validate. Maximum 100 per batch. / "
        "要验证的纳米抗体序列列表。每批最多100个。",
    )
    user_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional user identifier for batch submission. / "
        "批量提交的可选用户标识符。",
    )

    @field_validator("sequences")
    @classmethod
    def validate_sequences(cls, v: List[str]) -> List[str]:
        """Validate all sequences in batch. / 验证批次中的所有序列。"""
        validated = []
        for i, seq in enumerate(v):
            seq = seq.upper().strip()
            seq = re.sub(r"\s+", "", seq)
            invalid_chars = set(seq) - AMINO_ACIDS
            if invalid_chars:
                raise ValueError(
                    f"Sequence {i}: Invalid amino acid characters: "
                    f"{sorted(invalid_chars)}. / "
                    f"序列 {i}：无效的氨基酸字符：{sorted(invalid_chars)}。"
                )
            if len(seq) < 50 or len(seq) > 200:
                raise ValueError(
                    f"Sequence {i}: Length {len(seq)} outside valid range [50, 200]. / "
                    f"序列 {i}：长度 {len(seq)} 超出有效范围 [50, 200]。"
                )
            validated.append(seq)
        return validated

    class Config:
        """Pydantic configuration. / Pydantic 配置。"""

        json_schema_extra = {
            "example": {
                "sequences": [
                    "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS",
                    "QVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS",
                ],
                "user_id": "user_12345",
            }
        }





