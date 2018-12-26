import datetime
import os
import traceback
import csv
import time
import json

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException

from concurrent.futures.thread import ThreadPoolExecutor

CSV_FIELDS = ["site", "length",  "price", "start_date", "end_date", 'hyperlink', 'url']
CHROME_DRIVER = os.path.join(os.getcwd(), "chromedriver")
WORKER_COUNT = 3
executor = ThreadPoolExecutor(WORKER_COUNT)


def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920x1080")
    return webdriver.Chrome(options=chrome_options, executable_path=CHROME_DRIVER)


class DriverList(object):
    def __init__(self, driver_count):
        self._driver_list = []
        for i in range(driver_count):
            d = get_chrome_driver()
            d.is_locked = False
            self._driver_list.append(d)

    def get_available_driver(self):
        for d in self._driver_list:
            if not d.is_locked:
                d.is_locked = True
                return d

    def close(self):
        for d in self._driver_list:
            d.close()


class ResultSaver(object):
    def __init__(self):
        self._res_list = []

    def add_res(self, res):
        self._res_list.append(res)

    def get_res_list(self):
        return self._res_list

    def dump_to_json(self, path):
        with open(path, "w") as f:
            f.write(json.dumps(self._res_list))

    def dump_to_csv(self, path):
        with open(path, "w") as f:
            dw = csv.DictWriter(f, CSV_FIELDS)
            dw.writeheader()
            dw.writerows(self._res_list)


class WeSki(object):
    SITES = {
             1: 'Val Thorens',
             11: 'Avoriaz',
             4: 'La Plagne',
             3: 'Tignes',
             13: 'Val D\'isere',
             10: 'Les Arcs',
             12: 'Meribel',
             8: 'Las Deux Alps',
             5: 'Chamonix',
             2: 'Courchevel',
             9: 'Serre Chevalier',
             6: 'Les Menuires',
             7: ' Alpe D\'Huez'
    }

    SEARCH_URL = 'https://www.weski.co.il/package_search/new?utf8=%E2%9C%93&%5B'\
                 'from%5D=TLV&%5Bski_site_id%5D={2}&trip_dates={0}+-+{1}&%5Bgroup_s'\
                 'ize%5D=4'

    @staticmethod
    def _format_time(time_obj):
        return time_obj.strftime("%d/%m/%Y")

    @staticmethod
    def extract_data(site_id, start_date, length, result_saver, driver_list):
        site_name = WeSki.SITES[site_id]
        print(f"Starting scrape for {site_name} for {length} days starting {start_date}")
        try:
            driver = driver_list.get_available_driver()
            if not driver:
                print("Got no driver. Return.")
                return
            str_start_date = WeSki._format_time(start_date)
            str_end_date = WeSki._format_time(start_date + datetime.timedelta(days=length))
            url = 'https://www.weski.co.il/package_search/new?utf8=%E2%9C%93&%5B'\
                'from%5D=TLV&%5Bski_site_id%5D={2}&trip_dates={0}+-+{1}&%5Bgroup_s'\
                'ize%5D=4'.format(str_start_date, str_end_date, site_id)
            driver.get(url)
        except Exception as e:
            traceback.print_exc()
            return

        try:
            price = WebDriverWait(driver, 120).until(
                expected_conditions.visibility_of_element_located((By.CLASS_NAME, "value"))
            )
            if int(price.text.replace(",", "")) < 800:
                print("Got a price that seems to be too low: {0}".format(price.text))
                time.sleep(60)
                price = driver.find_element_by_class_name("value")
        except TimeoutException:
            print(f"Time Limit Exceeded, Passing This loop for {site_name} for {length} days starting {start_date}")
            driver.is_locked = False
            return
        except:
            traceback.print_exc()
            driver.is_locked = False
            return

        res = {
            'price': price.text,
            'start_date': str_start_date,
            'end_date': str_end_date,
            'length': length,
            'site': site_name,
            'url': url,
            'hyperlink': '=HYPERLINK("{0}", "Link")'.format(url),
        }

        result_saver.add_res(res)
        print(res)
        driver.is_locked = False


def print_results(res_saver):
    print(res_saver.get_res_list())


def main():
    driver_list = DriverList(WORKER_COUNT)
    try:
        time.sleep(20)
        result_saver = ResultSaver()

        start_date = datetime.datetime(2019, 1, 10)
        end_date = datetime.datetime(2019, 1, 20)
        min_length = 7
        max_length = 8
        for site in WeSki.SITES:
            current_date = start_date
            while current_date <= end_date:
                for length in range(min_length, max_length + 1):
                    executor.submit(WeSki.extract_data, site, current_date, length, result_saver, driver_list)
                current_date += datetime.timedelta(1)

        executor.shutdown()
        result_saver.dump_to_csv("new6.csv")
        result_saver.dump_to_json("new6.json")

    finally:
        driver_list.close()


if __name__ == '__main__':
    main()
