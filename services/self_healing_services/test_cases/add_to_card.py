# test_cases/test_add_to_cart.py
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Callable, Any

logger = logging.getLogger(__name__)

def run_add_item_test(driver: Any, healing_find_func: Callable, test_id: str, **kwargs):
    """
    Kịch bản Happy Path:
    1. Tải trang
    2. Thêm 'Brocolli' vào giỏ hàng
    3. Mở giỏ hàng và xác nhận 'Brocolli' có ở đó
    """
    logger.info(f"--- Bắt đầu kịch bản test: {test_id} ---")
    
    test_context = {
        "test_id": test_id,
        "test_case_priority": "medium", 
        "commit_info": {"hash": "N/A", "author": "Demo User"}
    }

    # === PHẦN 1: Tải trang ===
    app_url = "https://rahulshettyacademy.com/seleniumPractise/#/" 
    driver.get(app_url)
    test_context["page_url"] = app_url
    logger.info(f"Đã mở trang: {app_url}")
    
    # === PHẦN 2: Tìm và Thêm 'Brocolli' ===
    # <<< SỬA LỖI: Đã xóa 'driver=driver' >>>
    brocolli_add_btn = healing_find_func(
        by=By.XPATH,
        value="//h4[contains(text(),'Brocolli')]/following-sibling::div[@class='product-action']/button",
        element_name="HomePage_Button_AddBrocolli",
        test_context=test_context
    )
    brocolli_add_btn.click()
    logger.info("Đã thêm 'Brocolli' vào giỏ hàng.")

    # === PHẦN 3: Mở giỏ hàng và Xác nhận ===
    # <<< SỬA LỖI: Đã xóa 'driver=driver' >>>
    cart_icon = healing_find_func(
        by=By.CLASS_NAME,
        value="cart-icon",
        element_name="HomePage_Icon_Cart",
        test_context=test_context
    )
    cart_icon.click()
    logger.info("Đã mở giỏ hàng (cart preview).")

    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-preview .product-name"))
    )
    
    # <<< SỬA LỖI: Đã xóa 'driver=driver' >>>
    product_name_in_cart = healing_find_func(
        by=By.CSS_SELECTOR,
        value=".cart-preview .product-name",
        element_name="CartPreview_Text_ProductName",
        test_context=test_context
    )
    
    assert "Brocolli" in product_name_in_cart.text
    logger.info(f"Xác nhận thành công: '{product_name_in_cart.text}' có trong giỏ hàng.")
    
    logger.info(f"--- Kịch bản test: {test_id} THÀNH CÔNG ---")