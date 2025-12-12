# File: services/self_healing_services/test_cases/add_to_card.py

import logging
from typing import Any, Callable, Optional, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

logger = logging.getLogger(__name__)

def run_minimal_shop_happy_test(
    driver: Any,
    healing_find_func: Callable,
    test_id: str,
    run_id: Optional[int],
    **kwargs
):
    logger.info(f"=== [HappyCase-MinimalShop] Start: {test_id} (run_id={run_id}) ===")

    test_context: Dict[str, Any] = {
        "test_id": test_id,
        "run_id": run_id,
        "test_case_priority": "medium",
        "commit_info": {
            "hash": kwargs.get("git_hash", "N/A"),
            "author": kwargs.get("author", "local-user"),
            "build_version": kwargs.get("build_version", "local-build"),
            "app_version": kwargs.get("app_version", "1.0.0"),
        },
    }

    try:
        # ---------------- Step 1: Open homepage ----------------
        app_url = "https://minimal-shop-git-main-xuyns-projects.vercel.app/"
        driver.get(app_url)
        test_context["page_url"] = driver.current_url
        logger.info("[MinimalShop] Home page opened")

        # ---------------- Step 2: Click product card ----------------
        product_card = healing_find_func(
            by=By.XPATH,
            value='//h3[normalize-space()="Linen Throw Pillow"]',
            element_name="PRODUCT_CARD_LINEN_THROW_PILLOW",
            test_context=test_context,
        )
        
        # [FIX] Kiểm tra element trước khi tương tác
        if not product_card:
            raise NoSuchElementException("Healing Failed: Không tìm thấy PRODUCT_CARD_LINEN_THROW_PILLOW")
            
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(product_card))
        product_card.click()
        logger.info("[MinimalShop] Clicked product card")

        # ---------------- Step 3: Click Add to Cart ----------------
        add_to_cart_btn = healing_find_func(
            by=By.XPATH,
            value='//button[normalize-space()="Add to Bag"]',
            element_name="MODAL_BUTTON_ADD_TO_CART",
            test_context=test_context,
        )

        # [FIX] Kiểm tra element trước khi tương tác (Lỗi TypeError cũ nằm ở đây)
        if not add_to_cart_btn:
             raise NoSuchElementException("Healing Failed: Không tìm thấy MODAL_BUTTON_ADD_TO_CART")

        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(add_to_cart_btn))
        add_to_cart_btn.click()
        logger.info("[MinimalShop] Clicked Add to Cart")

        # # ---------------- Step 4: Verify Cart Drawer ----------------
        # cart_item = healing_find_func(
        #     by=By.XPATH,
        #     value='//h2[normalize-space()="Shopping Cart"]/following::h3[normalize-space()="Linen Throw Pillow"]',
        #     element_name="CART_ITEM_LINEN_THROW_PILLOW",
        #     test_context=test_context,
        # )
        
        # if not cart_item:
        #      raise NoSuchElementException("Healing Failed: Không tìm thấy CART_ITEM_LINEN_THROW_PILLOW")

        # assert cart_item.is_displayed(), "Cart item not visible!"
        # logger.info("[MinimalShop] Cart drawer contains product")

        # ---------------- Step 5: Click Checkout ----------------
        checkout_btn = healing_find_func(
            by=By.XPATH,
            value='//button[normalize-space()="Checkout"]',
            element_name="BUTTON_CHECKOUT",
            test_context=test_context,
        )

        if not checkout_btn:
             raise NoSuchElementException("Healing Failed: Không tìm thấy BUTTON_CHECKOUT")

        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(checkout_btn))
        checkout_btn.click()
        logger.info("[MinimalShop] Clicked Checkout")


    except Exception as e:
        logger.error(f"[MinimalShop] Test FAILED: {test_id} due to {type(e).__name__} - {e}")
        raise