import random
import string
import time
from pathlib import Path


def write_a_file(tmp_path: Path, name: str = None) -> None:
    """https://www.youtube.com/shorts/qG1LG1gADog"""
    if name is None:
        name = "EVENT_" + "".join(random.sample(string.ascii_uppercase, 10))
    print(name)
    with open(Path(tmp_path) / name, "w") as f:
        f.write(name)


def write_a_file_sleepy(tmp_path: Path, name: str = None) -> None:
    """Do it but also sleep for no reason"""
    if name is None:
        name = "EVENT_" + "".join(random.sample(string.ascii_uppercase, 10))

    with open(Path(tmp_path) / name, "w") as f:
        f.write(name)
        f.write("\n" + str(time.time()))
    time.sleep(0.1)
    print(name)
    with open(Path(tmp_path) / name, "a") as f:
        f.write("\n" + str(time.time()))
