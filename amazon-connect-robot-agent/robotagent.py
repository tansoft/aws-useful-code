from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import argparse
import time

parser = argparse.ArgumentParser()
parser.description="Robot Agent for Amazon Connect"
parser.add_argument("-a", "--alias", help="Specify instance alias", type=str, required=True)
parser.add_argument("-u", "--username", help="Specify user name", type=str, required=True)
parser.add_argument("-p", "--password", help="Specify user password", type=str, required=True)
parser.add_argument("--debug", help="Debug mode", action='store_true')
args = parser.parse_args()

options = Options()
if not args.debug:
    options.add_argument("--headless")
    options.add_argument("window-size=1920,1080")
    #https://stackoverflow.com/questions/38832776/how-do-i-allow-chrome-to-use-my-microphone-programmatically
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--use-fake-device-for-media-stream")
    options.add_argument("--allow-file-access-from-files")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
# chrome 权限允许，1:allow, 2:block
options.add_experimental_option("prefs", {
    "profile.default_content_setting_values.media_stream_mic": 1,
    "profile.default_content_setting_values.media_stream_camera": 1,
    "profile.default_content_setting_values.geolocation": 1,
    "profile.default_content_setting_values.notifications": 1
})

driver = webdriver.Chrome(options=options)

#页面加载等待最多 20 秒
print('opening ' + args.alias + ' ...')
driver.implicitly_wait(20)
driver.get('https://'+args.alias+'.my.connect.aws/')

wait = WebDriverWait(driver, 20)
try:
    # 登录页面
    wait.until(EC.presence_of_element_located((By.ID,'wdc_username')))
    wait.until(EC.presence_of_element_located((By.ID,'wdc_password')))
    wait.until(EC.presence_of_element_located((By.ID,'wdc_login_button')))
    driver.find_element(By.ID,'wdc_username').send_keys(args.username)
    driver.find_element(By.ID,'wdc_password').send_keys(args.password)
    print('try to login with user: ' + args.username + ' ...')
    driver.find_element(By.ID,'wdc_login_button').click()
    #打开连接页面，等待新窗口完成并切换
    wait.until(EC.presence_of_element_located((By.ID,'ccpLink')))
    original_window = driver.current_window_handle
    print('try to open ccpLink window ...')
    driver.find_element(By.ID,'ccpLink').click()
    wait.until(EC.number_of_windows_to_be(2))
    # 循环执行，直到找到一个新的窗口句柄
    for window_handle in driver.window_handles:
        if window_handle != original_window:
            print('try to switch to ccpLink window ...')
            driver.switch_to.window(window_handle)
            break
    # 等待新标签页完成加载内容
    print('waiting for panel init ...')
    #wait.until(EC.title_is("Amazon Connect Contact Control Panel"))
    #wait.until(EC.presence_of_element_located((By.ID,'agent-status-current')))
    wait.until(EC.text_to_be_present_in_element((By.ID,'agent-status-current'), 'Change Status')) #Change Status from the dropdown
    print('waiting for get change status ...')
    wait.until_not(EC.text_to_be_present_in_element((By.ID,'agent-status-current'), 'Change Status'))
    status = driver.find_element(By.ID, 'agent-status-current').text
    print('current status is: ' + status)
    if status == 'Offline' :
        #需要进行Agent上线操作
        print('try to open dropdown list ...')
        driver.find_element(By.ID, 'agent-status-dropdown').click();
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'#agent-status-dropdown + ul li')))
        print('try to find available menu ...')
        for li in driver.find_elements(By.CSS_SELECTOR,'#agent-status-dropdown + ul li'):
            if li.text == 'Available':
                print('waiting for available menu change to clickable...')
                wait.until(EC.element_to_be_clickable(li))
                li.click()
                print('finished...')
                break
except Exception as e:
    print(e)
    driver.close()

# ensure screen process not to exit
while True:
    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), ' sleeping...')
    time.sleep(3600)

#driver.close()
#driver.quit()
