import sys

project_home = '/home/3088737994/mysite'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

from app import app as application
