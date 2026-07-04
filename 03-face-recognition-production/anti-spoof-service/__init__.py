# coding=utf-8

# import all modules end with *_service.py

import os

abs_path = os.path.dirname(os.path.abspath(__file__))
for module_fname in os.listdir(abs_path):
    if "service.py" not in module_fname:
        continue
    module_name = "service." + module_fname.split(".")[0]
    __import__(module_name)  # import service.keboot_demo_service
