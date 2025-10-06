from contextlib import contextmanager
import os

@contextmanager
def open_utf8(path, mode="a"):
    full_path = os.path.abspath(path)
    f = open(full_path, mode, encoding="utf-8")
    try:
        yield f
    finally:
        f.close()
