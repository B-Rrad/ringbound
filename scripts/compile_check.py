import py_compile
import glob
import sys

files = ["main.py"] + glob.glob("ui/*.py")
exit_code = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        print("ERROR", f, e)
        exit_code = 1

sys.exit(exit_code)
