import sys
import os
APP_PATH = "/var/www/jurist-rus/jurist-rus-app-company"
sys.path.insert(0, APP_PATH)
os.chdir(APP_PATH)
# flaskapp.py is inside APP_PATH folder.
from flaskapp import app as application
