#!/usr/bin/python
import yaml
import logging
from typing import Union


def sort_yaml_file(file_name: str, dst_file_name: Union[str, None] = None):
    if not dst_file_name:
        dst_file_name = file_name

    with open(file_name, "r") as source_file:
        data = yaml.safe_load(source_file)

        if not ("indexes" in data):
            logging.error(f"There is no indexes main in file {file_name}")
            return

        data["indexes"] = sorted(data["indexes"], key=lambda k: k["kind"] if isinstance(k, dict) and "kind" in k else k)

        with open(dst_file_name, "a+") as dst_file:
            dst_file.seek(0)
            dst_file.truncate()
            dst_file.write(
                yaml.dump(data).replace("- kind: ", "\n- kind: ")
            )
            logging.info(f"Successfully sorted the yaml file {file_name} into {dst_file_name}")


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    try:
        sort_yaml_file("index.yaml")
    except FileNotFoundError:
        logging.error("index.yaml not present!")
