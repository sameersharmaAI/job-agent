# ==============================================================================
# FILE: tools/browser_tools.py
# PURPOSE: Manages the Selenium WebDriver instance.
# ==============================================================================
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
import shutil, os, tempfile


def get_webdriver():
    print("[Browser] Using Snap Firefox + geckodriver (ARM64)...")

    # Paths for snap firefox + geckodriver
    firefox_bin = "/snap/firefox/current/usr/lib/firefox/firefox"
    geckodriver = shutil.which("geckodriver") or "/snap/bin/geckodriver"

    if not os.path.exists(firefox_bin):
        print(f"[Browser] ERROR: Firefox binary not found at {firefox_bin}")
        return None
    if not os.path.exists(geckodriver):
        print(f"[Browser] ERROR: geckodriver not found at {geckodriver}")
        return None

    # Firefox options
    opts = FirefoxOptions()
    opts.binary_location = firefox_bin
    opts.add_argument("-headless")
    opts.add_argument("--no-remote")

    # Use a temp profile to bypass Snap's user data dir restrictions
    profile_dir = tempfile.mkdtemp(prefix="ff-profile-")
    opts.set_preference("browser.cache.disk.enable", False)
    opts.set_preference("browser.cache.memory.enable", False)
    opts.set_preference("browser.cache.offline.enable", False)
    opts.set_preference("network.http.use-cache", False)

    return webdriver.Firefox(service=FirefoxService(geckodriver), options=opts)