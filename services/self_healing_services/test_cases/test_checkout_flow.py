# test_cases/test_checkout_happy.py
import logging
from typing import Callable, Any, Optional, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


def run_checkout_happy_test(
    driver: Any,
    healing_find_func: Callable,
    test_id: str,
    run_id: Optional[int],
    **kwargs
):
    """
    Happy case chuẩn workflow mới:
      - Tất cả locator đều ĐÚNG
      - healing_find_func vẫn được dùng để nếu sau này break thì auto-heal
    """
    logger.info(f"=== [HappyCase] Start: {test_id} (run_id={run_id}) ===")

    test_context: Dict[str, Any] = {
        "test_id": test_id,
        "run_id": run_id,
        "test_case_priority": "high",
        "commit_info": {
            "hash": kwargs.get("git_hash", "N/A"),
            "author": kwargs.get("author", "local-user"),
            "build_version": kwargs.get("build_version", "local-build"),
            "app_version": kwargs.get("app_version", "1.0.0"),
        },
    }

    # 1) Open home
    app_url = "https://rahulshettyacademy.com/seleniumPractise/#/"
    driver.get(app_url)
    test_context["page_url"] = app_url
    logger.info("[HappyCase] Opened home")

    # 2) Add Cucumber
    healing_find_func(
        by=By.XPATH,
        value="//h4[contains(text(),'Cucumber')]/following-sibling::div[@class='product-action']/button",
        element_name="HomePage_Button_AddCucumber",
        test_context=test_context,
    ).click()
    logger.info("[HappyCase] Added Cucumber")

    # 3) Cart icon -> Proceed checkout
    healing_find_func(
        by=By.CLASS_NAME,
        value="cart-icon",
        element_name="HomePage_Icon_Cart",
        test_context=test_context,
    ).click()

    healing_find_func(
        by=By.XPATH,
        value="//button[text()='PROCEED TO CHECKOUT']",
        element_name="CartPreview_Button_Checkout",
        test_context=test_context,
    ).click()
    logger.info("[HappyCase] Proceeded to checkout")

    # 4) Apply promo
    WebDriverWait(driver, 10).until(EC.url_contains("/#/cart"))
    test_context["page_url"] = driver.current_url

    promo_code_input = healing_find_func(
        by=By.CLASS_NAME,
        value="promoCode",
        element_name="CartPage_Input_PromoCode",
        test_context=test_context,
    )
    promo_code_input.send_keys("rahulshettyacademy")

    healing_find_func(
        by=By.CLASS_NAME,
        value="promoBtn",
        element_name="CartPage_Button_ApplyPromo",
        test_context=test_context,
    ).click()

    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CLASS_NAME, "promoInfo"))
    )
    logger.info("[HappyCase] Promo applied")

    # 5) Place Order (LOCATOR ĐÚNG)
    place_order_btn = healing_find_func(
        by=By.XPATH,
        value="//button[normalize-space()='Place Order']",
        element_name="CartPage_Button_PlaceOrder",
        test_context=test_context,
    )
    place_order_btn.click()
    logger.info("[HappyCase] Clicked Place Order")

    # 6) Verify
    WebDriverWait(driver, 10).until(EC.url_contains("/#/country"))
    assert "/#/country" in driver.current_url

    logger.info(f"=== [HappyCase] SUCCESS: {test_id} ===")


# import logging
# import time
# from typing import Callable, Any, Optional, Dict

# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC

# logger = logging.getLogger(__name__)


# def run_checkout_healenium_native_sim_test(
#     driver: Any,
#     healing_find_func: Callable,
#     test_id: str,
#     run_id: Optional[int],
#     **kwargs,
# ):
#     """
#     Test case kích hoạt Healenium native (Tầng 1) bằng cách phá locator thật sự.
#     - Driver phải đi qua Healenium proxy (8085) như run_test.py của bạn.
#     - healing_find_func của manager sẽ:
#         Tầng 1: driver.find_element (native heal qua proxy)
#         Tầng 2: nếu native fail -> Python fallback

#     Phá DOM:
#       - Tìm nút Place Order theo baseline_xpath
#       - Replace node bằng 1 button mới có text khác
#       => baseline_xpath chắc chắn FAIL trên raw DOM
#     """

#     logger.info(f"=== [HealeniumNativeSim] Start test: {test_id} (run_id={run_id}) ===")

#     test_context: Dict[str, Any] = {
#         "test_id": test_id,
#         "run_id": run_id,
#         "page_url": None,
#         "test_case_priority": "medium",
#         "commit_info": {
#             "hash": kwargs.get("git_hash", "N/A"),
#             "author": kwargs.get("author", "local-user"),
#             "build_version": kwargs.get("build_version", "local-build"),
#             "app_version": kwargs.get("app_version", "1.0.0"),
#         },
#     }

#     # 1) Open home
#     app_url = "https://rahulshettyacademy.com/seleniumPractise/#/"
#     driver.get(app_url)
#     test_context["page_url"] = app_url
#     logger.info("[HealeniumNativeSim] Opened home page.")

#     # 2) Add Cucumber
#     healing_find_func(
#         by=By.XPATH,
#         value="//h4[contains(text(),'Cucumber')]/following-sibling::div[@class='product-action']/button",
#         element_name="HomePage_Button_AddCucumber",
#         test_context=test_context,
#     ).click()

#     # 3) Cart icon -> Proceed checkout
#     healing_find_func(
#         by=By.CLASS_NAME,
#         value="cart-icon",
#         element_name="HomePage_Icon_Cart",
#         test_context=test_context,
#     ).click()

#     healing_find_func(
#         by=By.XPATH,
#         value="//button[text()='PROCEED TO CHECKOUT']",
#         element_name="CartPreview_Button_Checkout",
#         test_context=test_context,
#     ).click()

#     WebDriverWait(driver, 10).until(EC.url_contains("/#/cart"))
#     test_context["page_url"] = driver.current_url

#     # 4) Apply promo
#     promo_input = healing_find_func(
#         by=By.CLASS_NAME,
#         value="promoCode",
#         element_name="CartPage_Input_PromoCode",
#         test_context=test_context,
#     )
#     promo_input.send_keys("rahulshettyacademy")

#     healing_find_func(
#         by=By.CLASS_NAME,
#         value="promoBtn",
#         element_name="CartPage_Button_ApplyPromo",
#         test_context=test_context,
#     ).click()

#     WebDriverWait(driver, 10).until(
#         EC.visibility_of_element_located((By.CLASS_NAME, "promoInfo"))
#     )
#     logger.info("[HealeniumNativeSim] Promo applied.")

#     # ------------------------------------------------------------
#     # 5) PHÁ LOCATOR THẬT SỰ: replace node cũ bằng node mới
#     # ------------------------------------------------------------
#     baseline_xpath = "//button[normalize-space()='Place Order']"
#     logger.warning("[HealeniumNativeSim] Simulating HARD DOM break (replace Place Order button)...")

#     js_break = """
#         var xpath = arguments[0];
#         var res = document.evaluate(xpath, document, null,
#                                     XPathResult.FIRST_ORDERED_NODE_TYPE, null);
#         var btn = res.singleNodeValue;
#         if (btn) {
#             btn.textContent = 'Place Order Now';
#             return true;
#         }
#         return false;
#         """


#     replaced = driver.execute_script(js_break, baseline_xpath)
#     logger.info(f"[HealeniumNativeSim] DOM replace executed: {replaced}")

#     # chờ DOM ổn định
#     time.sleep(0.5)

#     # ------------------------------------------------------------
#     # 6) GỌI LẠI LOCATOR CŨ QUA healing_find_func()
#     #    - Native heal sẽ chạy trước (qua proxy)
#     #    - Nếu native fail -> manager fallback Python
#     # ------------------------------------------------------------
#     logger.info(
#         "[HealeniumNativeSim] Calling healing_find_func with OLD locator. "
#         "This MUST fail on raw DOM -> expect native heal."
#     )

#     healed_btn = healing_find_func(
#         by=By.XPATH,
#         value=baseline_xpath,
#         element_name="CartPage_Button_PlaceOrder",
#         test_context=test_context,
#     )

#     healed_btn.click()
#     logger.info("[HealeniumNativeSim] Clicked healed Place Order Now.")

#     # 7) Verify
#     WebDriverWait(driver, 10).until(EC.url_contains("/#/country"))
#     assert "/#/country" in driver.current_url

#     logger.info(f"=== [HealeniumNativeSim] SUCCESS: {test_id} ===")

