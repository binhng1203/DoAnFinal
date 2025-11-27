# self_healing/wrapper.py
import logging
from typing import Any, Dict, Optional

from selenium.webdriver.remote.webdriver import WebDriver

from .manager import HealingManager

logger = logging.getLogger(__name__)


class HealingWrapper:
    """
    Wrapper mỏng cho self-healing, dùng lại toàn bộ logic trong HealingManager.

    - Tầng 1 (Healenium native) + Tầng 2 (Python fallback) + element validation
      đều được điều phối bởi HealingManager.get_healing_find_function().
    - Wrapper này chỉ cung cấp API tiện dụng cho test code.
    """

    def __init__(self, manager: HealingManager):
        self.manager = manager

    def find_element(
        self,
        driver: WebDriver,
        by: str,
        value: str,
        element_name: str,
        test_context: Optional[Dict[str, Any]] = None,
    ) -> object:
        """
        API tiện dụng:

        Thay vì test gọi trực tiếp healing_find_func(...),
        có thể gọi wrapper.find_element(...).

        Bên dưới sẽ dùng HealingManager.get_healing_find_function(driver),
        nên:
          - Tầng 1: thử native/Healenium trước
          - Tầng 2: nếu native fail → Python fallback (heal pipeline)
          - Có element-level validation theo config của manager
        """
        if test_context is None:
            test_context = {}

        healing_find_func = self.manager.get_healing_find_function(driver)

        logger.info(
            f"[HealingWrapper] Gọi healing_find_func cho '{element_name}' "
            f"(by={by}, value={value})"
        )

        return healing_find_func(
            by=by,
            value=value,
            element_name=element_name,
            test_context=test_context,
        )

    def validate_fullscreen(
        self,
        driver: WebDriver,
        page_name: str,
        test_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Helper để test có thể gọi fullscreen validation qua wrapper.

        Thực chất chỉ forward xuống HealingManager.validate_fullscreen().
        """
        logger.info(
            f"[HealingWrapper] Gọi fullscreen validation cho page '{page_name}'"
        )
        return self.manager.validate_fullscreen(
            driver=driver,
            page_name=page_name,
            test_context=test_context or {},
        )
