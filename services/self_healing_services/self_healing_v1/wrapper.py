# self_healing/wrapper.py
import logging
from typing import Any, Dict, Optional

from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver

from .manager import HealingManager
from .context import HealingContext

logger = logging.getLogger(__name__)


class HealingWrapper:
    """
    Wrapper chuẩn cho self-healing:
    
    TẦNG 1: Healenium native (qua proxy 8085)
        - driver.find_element() luôn được thử trước
        - Log rõ ràng native-found / native-failed
        - Bắt được cả NoSuchElementException & WebDriverException

    TẦNG 2: Python fallback (4-layer)
        - Chỉ chạy khi native fail thật sự
        - Có thể tắt fallback hoặc bật chế độ native-only
        - Đồng bộ hoàn toàn với HealingManager.heal()
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

        if test_context is None:
            test_context = {}

        # Dùng để ép native-only trong testcase
        native_only_mode = bool(test_context.get("native_only", False))

        # ======================= 
        #  TẦNG 1 — Healenium Native
        # =======================
        try:
            el = driver.find_element(by, value)
            logger.info(
                f"[HealingWrapper] (T1-native) FOUND: {element_name} "
                f"(by={by}, value={value})"
            )
            return el

        except (NoSuchElementException, WebDriverException) as e:
            # Báo native fail
            logger.warning(
                f"[HealingWrapper] (T1-native) NOT FOUND/NOT HEALED: {element_name} "
                f"(by={by}, value={value}); Exception={type(e).__name__}"
            )

            # ============================
            #  Native-only mode → fail thẳng
            # ============================
            if native_only_mode or not self.manager.enable_python_fallback:
                logger.error(
                    f"[HealingWrapper] Native-only mode: KHÔNG chạy fallback cho {element_name}."
                )
                raise NoSuchElementException(
                    f"Native Healenium failed for {element_name} "
                    f"(by={by}, value={value})"
                ) from e

        # =======================
        #  TẦNG 2 — Python Fallback
        # =======================
        logger.warning(
            f"[HealingWrapper] (T2-fallback) Kích hoạt pipeline self-healing Python cho '{element_name}'..."
        )

        context = HealingContext(
            driver=driver,
            broken_locator=(by, value),
            element_name=element_name,
            test_context=test_context,
        )

        healed_el = self.manager.heal(context)

        logger.info(
            f"[HealingWrapper] (T2-fallback) COMPLETED for '{element_name}'. "
            f"Healed -> {context.chosen_locator}"
        )

        return healed_el
