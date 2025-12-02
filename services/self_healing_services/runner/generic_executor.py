import logging
import time
from typing import Any, Dict, List, Callable

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


logger = logging.getLogger(__name__)

# Map locator_type (string trong DB) -> selenium By
_BY_MAPPING = {
    "id": By.ID,
    "xpath": By.XPATH,
    "css": By.CSS_SELECTOR,
    "css_selector": By.CSS_SELECTOR,
    "class_name": By.CLASS_NAME,
    "name": By.NAME,
    "link_text": By.LINK_TEXT,
    "partial_link_text": By.PARTIAL_LINK_TEXT,
    "tag_name": By.TAG_NAME,
}


def _build_by(locator_type: str, locator_value: str):
    if not locator_type:
        raise ValueError("locator_type is required for this action")
    if locator_type not in _BY_MAPPING:
        raise ValueError(f"Unsupported locator_type: {locator_type}")
    return _BY_MAPPING[locator_type], locator_value


def run_steps_test(
    driver: Any,
    healing_find_func: Callable,
    test_definition: Dict[str, Any],
    **kwargs,
):
    """
    Executor generic cho mọi testcase data-driven.

    test_definition:
      - "test_id"
      - "name"
      - "priority" (optional)
      - "steps": list các step, mỗi step có:
        + order
        + action
        + locator_type
        + locator_value
        + value
        + url
        + expected
        (+ element_name: optional, nếu sau này bạn thêm vào DB)
    """

    steps: List[Dict[str, Any]] = sorted(
        test_definition.get("steps", []),
        key=lambda s: s.get("order", 0),
    )

    timeout = kwargs.get("timeout", 10)

    test_id = str(test_definition.get("test_id", "unknown"))
    test_name = test_definition.get("name", "")
    test_priority = test_definition.get("priority", "medium")

    logger.info("=== [Executor] Start test: %s (%s) ===", test_name, test_id)

    # test_context tối thiểu cho Healenium
    base_test_context: Dict[str, Any] = {
        "test_id": test_id,
        "test_name": test_name,
        "test_case_priority": test_priority,
        "commit_info": {
            "hash": kwargs.get("git_hash", "N/A"),
            "author": kwargs.get("author", "system-api"),
            "build_version": kwargs.get("build_version", "api-build"),
            "app_version": kwargs.get("app_version", "1.0.0"),
        },
    }

    for step in steps:
        order = step.get("order")
        action = (step.get("action") or "").strip()
        locator_type = step.get("locator_type")
        locator_value = step.get("locator_value")
        value = step.get("value")
        url = step.get("url")
        expected = step.get("expected")

        # Tạo element_name “tạm xịn” (vì DB chưa có cột này)
        element_name = step.get("element_name")
        if not element_name:
            if locator_value:
                element_name = f"Step_{order}_{action}_{locator_value}"
            else:
                element_name = f"Step_{order}_{action}"

        # Clone test_context cho mỗi step
        test_context = dict(base_test_context)
        try:
            current_url = driver.current_url
        except Exception:
            current_url = None
        test_context["step_order"] = order
        test_context["step_action"] = action
        test_context["page_url"] = current_url

        logger.info(
            "[Executor] Step %s: action=%s, locator_type=%s, locator_value=%s, value=%s, url=%s, expected=%s, element_name=%s",
            order,
            action,
            locator_type,
            locator_value,
            value,
            url,
            expected,
            element_name,
        )

        try:
            # 1. OPEN_URL
            if action == "open_url":
                if not url:
                    raise ValueError("Step 'open_url' requires 'url'")
                driver.get(url)
                test_context["page_url"] = url

            # 2. CLICK
            elif action == "click":
                by, val = _build_by(locator_type, locator_value)
                el = healing_find_func(
                    by=by,
                    value=val,
                    element_name=element_name,
                    test_context=test_context,
                )
                el.click()

            # 3. TYPE
            elif action == "type":
                by, val = _build_by(locator_type, locator_value)
                el = healing_find_func(
                    by=by,
                    value=val,
                    element_name=element_name,
                    test_context=test_context,
                )
                el.clear()
                if value is not None:
                    el.send_keys(str(value))

            # 4. WAIT_SECONDS (optional)
            elif action == "wait_seconds":
                secs = float(value or 1)
                time.sleep(secs)

            # 5. ASSERT_URL_CONTAINS
            elif action == "assert_url_contains":
                if not expected:
                    raise ValueError("Step 'assert_url_contains' requires 'expected'")
                WebDriverWait(driver, timeout).until(
                    EC.url_contains(expected)
                )
                current = driver.current_url
                assert expected in current, (
                    f"[ASSERT_URL_CONTAINS] expected '{expected}' in '{current}'"
                )

            # 6. ASSERT_VISIBLE
            elif action == "assert_visible":
                by, val = _build_by(locator_type, locator_value)
                WebDriverWait(driver, timeout).until(
                    EC.visibility_of_element_located((by, val))
                )

            # 7. ASSERT_TEXT
            elif action == "assert_text":
                by, val = _build_by(locator_type, locator_value)
                el = healing_find_func(
                    by=by,
                    value=val,
                    element_name=element_name,
                    test_context=test_context,
                )
                actual = (el.text or "").strip()
                exp = (expected or "").strip()
                assert actual == exp, (
                    f"[ASSERT_TEXT] expected '{exp}', got '{actual}'"
                )

            # 8. ASSERT_TEXT_CONTAINS
            elif action == "assert_text_contains":
                by, val = _build_by(locator_type, locator_value)
                el = healing_find_func(
                    by=by,
                    value=val,
                    element_name=element_name,
                    test_context=test_context,
                )
                actual = (el.text or "").strip()
                exp = (expected or "").strip()
                assert exp in actual, (
                    f"[ASSERT_TEXT_CONTAINS] expected '{exp}' in '{actual}'"
                )

            else:
                raise ValueError(f"Unknown action: {action!r} in step {order}")

        except Exception as e:
            logger.exception(
                "[Executor] Error at step %s (action=%s): %s",
                order,
                action,
                e,
            )
            # Ném tiếp cho run_test_wrapper set failed + ghi custom_analytics
            raise

    logger.info("=== [Executor] SUCCESS: %s (%s) ===", test_name, test_id)
