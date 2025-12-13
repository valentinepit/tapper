import os
from selenium.webdriver.common.by import By


login_str = os.environ['WPLAN_LOGIN']
password = os.environ['WPLAN_PASS']


def login(driver) -> bool:
    try:
        driver.find_element(By.XPATH, "//input[@name='login']").send_keys(login_str)
        driver.find_element(By.XPATH, "//input[@name='password']").send_keys(password)
        driver.find_element(By.XPATH, "//button[@id='loginButton']").click()
        driver.implicitly_wait(10)
    except:
        return False
    return True


def start_stop_day(driver) -> bool:
    try:
        driver.find_element(By.XPATH, "//button[@id='startEndWorkButton']").click()
        driver.implicitly_wait(10)
    except:
        return False
    return True



