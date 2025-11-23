# self_healing_v1/__init__.py

"""
Self-healing v1 – phiên bản mới, ưu tiên Healenium là engine chính.
Python 4 layer chỉ chạy khi Healenium thất bại.
"""
from .manager import HealingManager
from .context import HealingContext

__all__ = ["HealingManager", "HealingContext"]

