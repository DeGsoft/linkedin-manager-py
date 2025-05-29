import os
from urllib.parse import urlencode, quote_plus
from loguru import logger as log
import re
import time
from playwright.sync_api import Playwright, sync_playwright, expect
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
LINKEDIN_LOGIN = os.getenv("LINKEDIN_LOGIN")
LINKEDIN_USER = os.getenv("LINKEDIN_USER")
LINKEDIN_PASS = os.getenv("LINKEDIN_PASS")
SUBJECT = os.getenv("LINKEDIN_SUBJECT")
MESSAGE_TEXT = os.getenv("LINKEDIN_MESSAGE")
ASSETS = './assets/'
EXCEL_PATH = ASSETS + os.getenv("EXCEL")


def wait(page, n=1):
    page.wait_for_load_state('load')
    time.sleep(n)


def send(context, page, df):
    for index, row in df.iterrows():
        # if row.invited != 'yes' and row.invited != 'not_found' and row.invited != 'connect' and row.invited != 'pending':
        if row.invited != 'yes' and row.invited != 'not_found' and row.invited != 'disabled':
            url = row.linkedin
            url = 'https://'+url.replace('https://', '')
            url = url.replace('/details/experience', '')
            print('url', url)
            page.goto(url)
            wait(page, 15)
            new_page_promise = None
            page.on(
                "page", lambda event: new_page_promise if event.page_id else False)
            page_content = page.content()
            with open(ASSETS + "profile.html", "w", encoding="utf-8") as f:
                f.write(page_content)
            page.screenshot(path=ASSETS + "screenshot.png")
            profile_name = page.locator("h1").text_content()
            connect = False
            connect = page.get_by_role("button", name=re.compile(
                rf"^Invita a {profile_name}.+")).count() > 0
            pending = False
            if (not connect):
                pending = page.get_by_role(
                    "button", name=re.compile(r"^Pendiente.+")).count() > 0
            follow = False
            if (not connect and not pending):
                follow = page.get_by_role(
                    "button", name=re.compile(r"^Seguir.+")).count() > 0
            if (not follow and not pending and not connect):
                page.get_by_role("button", name=re.compile(
                    r"^Enviar mensaje a .+")).click()
                wait(page, 5)
                page.get_by_role(
                    "textbox", name="Escribe un mensaje…").fill(f"Hola {profile_name.split()[0]}, {MESSAGE_TEXT}")
                wait(page, 5)
                page.get_by_role("button", name="Enviar", exact=True).click()
                wait(page, 10)
                df.loc[index, 'invited'] = 'yes'
                page.get_by_role(
                    "button", name="Cierra tu conversación con").click()
                wait(page, 60)
            else:
                page.get_by_role("button", name="Más acciones").click()
                wait(page)
                new_title = ""
                try:
                    with context.expect_page(timeout=20000) as new_page_info:
                        page.get_by_role("button", name=re.compile(
                            r"^Enviar mensaje a .+")).click()
                        wait(page, 15)
                        new_page = new_page_info.value
                        new_page.wait_for_load_state()
                        new_title = new_page.title()
                except TimeoutError:
                    print("New tab not found within the timeout period.")
                except Exception as e:
                    print(f"An unexpected error occurred on new tab: {e}")
                finally:
                    page.wait_for_load_state()
                if re.search(r"Sales Navigator", new_title):
                    wait(page, 5)
                    try:
                        new_page.fill(
                            'input[placeholder="Asunto (obligatorio)"]', SUBJECT)
                    except TimeoutError:
                        print("Element not found within the timeout period.")
                    except Exception as e:
                        print(f"An unexpected error occurred: {e}")
                    finally:
                        wait(new_page, 5)
                    new_page.fill('textarea[placeholder="Escribe aquí el mensaje…"]',
                                  f"Hola {profile_name.split()[0]}, {MESSAGE_TEXT}")
                    wait(new_page, 15)
                    new_page.wait_for_selector(
                        'button:has-text("Enviar")', state="visible")
                    new_page.hover('button:has-text("Enviar")')
                    new_page.click('button:has-text("Enviar")')
                    wait(new_page, 10)
                    df.loc[index, 'invited'] = 'yes'
                    wait(new_page, 5)
                    new_page.close()
                else:
                    page.get_by_role("textbox", name="Escribe un mensaje…").fill(
                        f"Hola {profile_name.split()[0]}, {MESSAGE_TEXT}")
                    wait(page, 15)
                    page.click(
                        "button.msg-form__send-btn[type='submit'], button.msg-form__send-button[type='submit']")
                    wait(page, 10)
                    df.loc[index, 'invited'] = 'yes'
                    page.get_by_role(
                        "button", name="Cierra el borrador de la conversación").click()
                    # df.loc[index, 'invited'] = 'pending' if pending else 'connect'
                    wait(page, 5)
            df.to_excel(EXCEL_PATH, index=False)


def run(df, playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    STATE_PATH = ASSETS + "state.json"
    if os.path.exists(STATE_PATH):
        context = browser.new_context(storage_state=ASSETS + "state.json")
    else:
        context = browser.new_context()
        page.goto(LINKEDIN_LOGIN)
        wait(page, 5)
        EMAIL_INPUT = "Email or phone"
        page.get_by_role("textbox", name=EMAIL_INPUT).click()
        page.get_by_role("textbox", name=EMAIL_INPUT).fill(LINKEDIN_USER)
        PASSWORD_INPUT = "Password"
        page.get_by_role("textbox", name=PASSWORD_INPUT).click()
        page.get_by_role("textbox", name=PASSWORD_INPUT).fill(LINKEDIN_PASS)
        page.get_by_role("button", name="Sign in", exact=True).click()
        wait(page, 60)
        context.storage_state(path=STATE_PATH)
    page = context.new_page()
    send(context, page, df)
    context.close()
    browser.close()


if __name__ == "__main__":
    df = pd.read_excel(EXCEL_PATH)
    with sync_playwright() as playwright:
        run(df, playwright)
