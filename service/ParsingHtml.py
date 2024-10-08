from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from axe_selenium_python import Axe
from time import sleep
from PIL import Image
import io
import numpy as np
import json

def pars_web_page(url):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get(url)

    axe = Axe(driver)

    # Запуск тестов доступности
    axe.inject()
    results = axe.run()

    sleep(5)

    html = driver.page_source

    check_scalability(driver)
    sleep(10)

    check_contrast(driver)

    check_description_image(driver)

    popup = find_popup_selector(driver)

    accessible = is_popup_keyboard_accessible(driver, popup)
    if accessible:
        print("Всплывающее окно доступно для управления с клавиатуры.")
    elif popup is not None:
        print("Всплывающее окно недоступно для управления с клавиатуры.")

    driver.quit()

    # Расчет итогового балла
    final_score = calculate_accessibility_score(results)

    # Вывод результата
    print(f"Итоговый балл доступности: {final_score:.2f}/100")

    # Вывод ошибок по важным критериям
    print_important_violations(results)

def check_size_page(driver):
    window_width = driver.execute_script("return window.innerWidth;")
    print(f'Ширина окна: {window_width}')

    # Получить ширину документа
    document_width = driver.execute_script("return document.body.scrollWidth;")
    print(f'Ширина документа: {document_width}')

    # Проверка наличия горизонтальной прокрутки
    if document_width > window_width:
        print("На сайте есть горизонтальное прокручивание.")
    else:
        print("На сайте нет горизонтального прокручивания.")

def check_contrast(driver):
    screenshot = driver.get_screenshot_as_png()

    # Откройте изображение с помощью Pillow
    image = Image.open(io.BytesIO(screenshot))

    # Преобразуйте изображение в градации серого
    gray_image = image.convert('L')

    # Преобразуйте изображение в массив numpy
    image_array = np.array(gray_image)

    # Вычислите контрастность
    contrast = image_array.std()

    print(f'Контрастность изображения: {contrast}')

def check_scalability(driver):
    meta_viewport = driver.execute_script(
        "return document.querySelector('meta[name=\"viewport\"]').getAttribute('content')"
    )

    # Эмуляция различных размеров экранов
    sizes = [(320, 480), (768, 1024), (1024, 768), (1920, 1080)]
    count_size = 0
    for width, height in sizes:
        driver.set_window_size(width, height)
        window_width = driver.execute_script("return window.innerWidth;")
        document_width = driver.execute_script("return document.body.scrollWidth;")

        # Проверка наличия горизонтальной прокрутки
        if document_width > window_width:
            count_size += 1
    if count_size > 0:
        print("При изменении масштаба появилась горизонтальная прокрутка")
    else:
        print("Сайт масштабируется правильно")

def check_description_image(driver):
    try:
        image = driver.find_element(By.TAG_NAME, 'img')
        alt_text = image.get_attribute('alt')

        if alt_text:
            print(f'Описание изображения: {alt_text}')
        else:
            print('Атрибут alt не найден.')
    except Exception as e:
        print("Ошибка при проверке описания изображения:", e)

def find_popup_selector(driver):
    potential_selectors = [
        "[role='dialog']",
        ".modal",
        ".popup",
        "#cookie-banner",
        "#cookieWarning",
        "#cookieHolder",
        ".cookie-banner",
        ".cookie-popup",
        ".cookie-consent",
        "[aria-label='cookie consent']",
        "[id*='cookie']",
        "[class*='cookie']"
    ]

    for selector in potential_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            if element.is_displayed():
                return element
    return None

def calculate_accessibility_score(results):
    violations = results['violations']

    # Начальный балл
    score = 100

    # Приоритеты для различных уровней серьезности
    priority_scores = {
        'critical': 0.5,
        'serious': 0.3,
        'moderate': 0.2,
        'minor': 0.1
    }

    # Критерии, которые несут только одну ошибку
    single_error_criteria = {
        'document-title',
        'heading-order'
    }

    print("\nДетали штрафов за ошибки:")
    for violation in violations:
        impact = violation['impact']
        nodes_count = len(violation['nodes'])

        # Получаем приоритетный балл
        priority_score = priority_scores.get(impact, 1)

        # Проверяем, является ли критерий таким, который несет только одну ошибку
        if violation['id'] in single_error_criteria:
            penalty = priority_score * 10
            print(f"Критерий: {violation['id']} | Приоритет: {priority_score} | Штраф: {priority_score} * 10 = {penalty}")
        else:
            penalty = priority_score * nodes_count
            print(f"Критерий: {violation['id']} | Приоритет: {priority_score} | Кол-во ошибок: {nodes_count} | Штраф: {priority_score} * {nodes_count} = {penalty}")

        # Вычитаем штраф из общего балла
        score -= penalty

    # Ограничение балла от 0 до 100
    final_score = max(min(score, 100), 0)
    save_results_to_json(final_score, results['violations'])
    return final_score

def is_popup_keyboard_accessible(driver, popup):
    if popup is None:
        print("Всплывающее окно не найдено.")
        return False

    focusable_elements = popup.find_elements(By.CSS_SELECTOR, 'a, button, input, select, textarea, [tabindex]')

    try:
        initial_focus = WebDriverWait(driver, 10).until(
            EC.visibility_of(focusable_elements[0])
        )
        initial_focus.send_keys(Keys.TAB)

        for element in focusable_elements:
            WebDriverWait(driver, 10).until(
                EC.visibility_of(element)
            )
            element.send_keys(Keys.TAB)
            if not element == driver.switch_to.active_element:
                return False
        return True
    except TimeoutException:
        print("Элемент не доступен для взаимодействия.")
        return False

def print_important_violations(results):
    important_criteria = [
        'keyboard',  # Использование клавиатуры
        'image-alt',  # Альтернативный текст для изображений
        'color-contrast',  # Контрастность текста
        'document-title',  # Заголовки страниц
        'label',  # Формы и их описание
        'aria-roles',  # Использование ARIA
        'heading-order'  # Структура заголовков
    ]

    print("\nОшибки по важным критериям:")
    for violation in results['violations']:
        if violation['id'] in important_criteria:
            print(f"\nКритерий: {violation['id']}")
            print(f"Описание: {violation['description']}")
            print(f"Количество элементов с ошибками: {len(violation['nodes'])}")

def save_results_to_json(final_score, violations):
    data = {
        "final_score": final_score,
        "criteria": []
    }

    for violation in violations:
        data["criteria"].append({
            "id": violation['id'],
            "description": violation['description'],
            "impact": violation['impact'],
            "errors_count": len(violation['nodes'])
        })

    with open('/Users/User/OneDrive/Документы/hakaton/ml-for-blinds/templates/accessibility_results.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Пример использования функции
# Предположим, что у вас уже есть `final_score` и `results` из `axe.run()`


