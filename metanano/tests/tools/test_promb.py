"""
References / 参考:
    - docs/en/TODO.md: Section 0.5 - promb Integration
    - docs/cn/TODO.md: 第0.5节 - promb 集成
    - promb GitHub: https://github.com/MSDLLCPapers/promb

File / 文件:
    - metanano/tests/tools/test_promb.py

Overview / 概述:
    Pytest tests for promb (OASis humanness) integration.
    promb（OASis 人源性）集成的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. promb package availability
        2. human-oas database loading
        3. Peptide content computation
        4. Average mutations scoring
        5. Integration with NativenessFilter (optional)

    Python API:
    Python API：
        import promb
        
        db = promb.init_db("human-oas")
        peptides = db.chop_seq_peptides(sequence)
        content = sum(db.contains(p) for p in peptides) / len(peptides)
        avg_mutations = db.compute_average_mutations(sequence)

    Output / 输出:
        - Content: Fraction of peptides found in OAS (0-1)
        - Average Mutations: Average number of mutations from OAS

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
from typing import Optional


def is_promb_available() -> bool:
    """
    Check if promb package is available.
    检查 promb 包是否可用。
    """
    try:
        import promb
        return True
    except ImportError:
        return False


def get_oas_db():
    """
    Get human-oas database instance.
    获取 human-oas 数据库实例。
    """
    import promb
    return promb.init_db("human-oas", verbose=False)


class TestPrombAvailability:
    """
    Test suite for promb package availability.
    promb 包可用性的测试套件。
    """

    def test_promb_installed(self) -> None:
        """
        Test that promb package is installed.
        测试 promb 包是否已安装。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        import promb
        assert promb is not None

    def test_promb_version(self) -> None:
        """
        Test that promb has version attribute.
        测试 promb 是否有版本属性。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        import promb
        assert hasattr(promb, '__version__')

    def test_init_db_available(self) -> None:
        """
        Test that init_db function is available.
        测试 init_db 函数是否可用。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        import promb
        assert hasattr(promb, 'init_db')
        assert callable(promb.init_db)


class TestPrombDatabase:
    """
    Test suite for promb database loading.
    promb 数据库加载的测试套件。
    """

    def test_load_human_oas_database(self) -> None:
        """
        Test loading the human-oas database.
        测试加载 human-oas 数据库。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        
        assert db is not None, "Database should be loaded"
        assert hasattr(db, 'peptide_length'), "DB should have peptide_length"
        assert db.peptide_length > 0, "Peptide length should be positive"

    def test_database_has_peptides(self) -> None:
        """
        Test that database contains peptides.
        测试数据库是否包含肽段。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        
        assert hasattr(db, 'peptides'), "DB should have peptides"
        # Note: peptides might be a generator or set
        # 注意：peptides 可能是生成器或集合

    def test_database_methods(self) -> None:
        """
        Test that required database methods exist.
        测试所需的数据库方法是否存在。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        
        required_methods = [
            'chop_seq_peptides',
            'contains',
            'compute_average_mutations',
        ]
        
        for method in required_methods:
            assert hasattr(db, method), f"DB should have '{method}' method"


class TestPeptideContent:
    """
    Test suite for peptide content computation.
    肽段内容计算的测试套件。
    """

    def test_chop_sequence_into_peptides(self, sample_sequence: str) -> None:
        """
        Test chopping sequence into peptides.
        测试将序列切割成肽段。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        peptides = db.chop_seq_peptides(sample_sequence)
        
        assert len(peptides) > 0, "Should produce peptides"
        assert all(len(p) == db.peptide_length for p in peptides), \
            "All peptides should have correct length"

    def test_peptide_contains(self, sample_sequence: str) -> None:
        """
        Test checking if peptide exists in OAS.
        测试检查肽段是否存在于 OAS 中。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        peptides = db.chop_seq_peptides(sample_sequence)
        
        # Check first peptide
        # 检查第一个肽段
        result = db.contains(peptides[0])
        
        assert isinstance(result, bool), "contains() should return bool"

    def test_compute_content_score(self, sample_sequence: str) -> None:
        """
        Test computing peptide content score.
        测试计算肽段内容分数。
        
        Content = fraction of peptides found in OAS database.
        内容 = 在 OAS 数据库中找到的肽段比例。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        peptides = db.chop_seq_peptides(sample_sequence)
        
        # Compute content manually
        # 手动计算内容
        content = sum(db.contains(p) for p in peptides) / len(peptides)
        
        assert 0.0 <= content <= 1.0, "Content should be in [0, 1]"

    def test_content_for_different_sequences(
        self, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test content scores for different sequences.
        测试不同序列的内容分数。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        
        peptides1 = db.chop_seq_peptides(sample_sequence)
        peptides2 = db.chop_seq_peptides(sample_sequence_2)
        
        content1 = sum(db.contains(p) for p in peptides1) / len(peptides1)
        content2 = sum(db.contains(p) for p in peptides2) / len(peptides2)
        
        # Both should produce valid scores
        # 两者都应该产生有效分数
        assert 0.0 <= content1 <= 1.0
        assert 0.0 <= content2 <= 1.0


class TestAverageMutations:
    """
    Test suite for average mutations computation.
    平均突变计算的测试套件。
    """

    def test_compute_average_mutations(self, sample_sequence: str) -> None:
        """
        Test computing average mutations from OAS.
        测试计算与 OAS 的平均突变。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        
        avg_mutations = db.compute_average_mutations(sample_sequence)
        
        assert isinstance(avg_mutations, float), "Should return float"
        assert avg_mutations >= 0.0, "Mutations should be non-negative"

    def test_identical_sequence_low_mutations(self) -> None:
        """
        Test that sequences in OAS have low average mutations.
        测试 OAS 中的序列平均突变较低。
        
        Note: This is a heuristic test - real OAS sequences should have 
        low mutation scores.
        注意：这是一个启发式测试 - 真实的 OAS 序列应该有较低的突变分数。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        # This test just verifies the API works
        # 此测试仅验证 API 工作
        db = get_oas_db()
        
        # The sample sequence should have some level of humanness
        # 示例序列应该有一定程度的人源性
        sample = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDLGWSFDYWGQGTLVTVSS"
        
        avg_mutations = db.compute_average_mutations(sample)
        
        # Just verify it returns a valid number
        # 只验证它返回有效数字
        assert avg_mutations >= 0.0

    def test_mutations_for_different_sequences(
        self, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test mutation scores for different sequences.
        测试不同序列的突变分数。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        db = get_oas_db()
        
        mutations1 = db.compute_average_mutations(sample_sequence)
        mutations2 = db.compute_average_mutations(sample_sequence_2)
        
        # Both should produce valid scores
        # 两者都应该产生有效分数
        assert mutations1 >= 0.0
        assert mutations2 >= 0.0


class TestPrombRunFunction:
    """
    Test suite for promb.run_promb function.
    promb.run_promb 函数的测试套件。
    """

    def test_run_promb_content_mode(self, sample_sequence: str) -> None:
        """
        Test run_promb with content mode.
        测试使用内容模式的 run_promb。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        import promb
        import tempfile
        import os
        
        db = get_oas_db()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fa', delete=False) as f:
            f.write(f">test\n{sample_sequence}\n")
            temp_path = f.name
        
        try:
            results, skipped = promb.run_promb(db, [temp_path], mode='content')
            
            assert not results.empty, "Should return results"
            assert 'Content' in results.columns, "Should have Content column"
            
            content = results['Content'].values[0]
            assert 0.0 <= content <= 1.0
        finally:
            os.unlink(temp_path)

    def test_run_promb_nearest_mode(self, sample_sequence: str) -> None:
        """
        Test run_promb with nearest mode.
        测试使用最近模式的 run_promb。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        import promb
        import tempfile
        import os
        
        db = get_oas_db()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fa', delete=False) as f:
            f.write(f">test\n{sample_sequence}\n")
            temp_path = f.name
        
        try:
            results, skipped = promb.run_promb(db, [temp_path], mode='nearest')
            
            assert not results.empty, "Should return results"
            assert 'Nearest' in results.columns, "Should have Nearest column"
            assert 'Mutations' in results.columns, "Should have Mutations column"
        finally:
            os.unlink(temp_path)


class TestNativenessFilterPrombIntegration:
    """
    Test suite for NativenessFilter integration with promb.
    NativenessFilter 与 promb 集成的测试套件。
    """

    def test_filter_can_use_promb_for_humanness(self, sample_sequence: str) -> None:
        """
        Test that NativenessFilter can use promb for humanness scoring.
        测试 NativenessFilter 可以使用 promb 进行人源性评分。
        """
        if not is_promb_available():
            pytest.skip("promb not installed")
        
        from metanano.config import NativenessConfig
        from metanano.filters.nativeness import NativenessFilter
        
        config = NativenessConfig()
        nat_filter = NativenessFilter(config)
        
        # Check if filter has humanness scoring capability
        # 检查过滤器是否有人源性评分能力
        result = nat_filter.analyze(sample_sequence)
        
        assert result is not None
        assert hasattr(result, 'passed')




