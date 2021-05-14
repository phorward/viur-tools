#!/usr/bin/env python3

__author__ = "Sven Eberth"
__email__ = "se@mausbrand.de"
__version__ = "1.1.0"

import argparse
import csv
import functools
import itertools
import logging
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Union

import requests

logging.basicConfig(
	format=f"%(asctime)s %(levelname)8s %(filename)s:%(lineno)03d :: %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def formatString(format, data, structure=None, prefix=None, language=None, _rec=0):  # from Vi v2.5
	"""
	Parses a string given by format and substitutes placeholders using values specified by data.

	The syntax for the placeholders is $(%s).
	Its possible to traverse to sub-dictionarys by using a dot as seperator.
	If data is a list, the result each element from this list applied to the given string; joined by ", ".

	Example:

		data = {"name": "Test","subdict": {"a":"1","b":"2"}}
		formatString = "Name: $(name), subdict.a: $(subdict.a)"

	Result: "Name: Test, subdict.a: 1"

	:param format: String containing the format.
	:type format: str

	:param data: Data applied to the format String
	:type data: list | dict

	:param structure: Parses along the structure of the given skeleton.
	:type structure: dict

	:return: The traversed string with the replaced values.
	:rtype: str
	"""

	if structure and isinstance(structure, list):
		structure = {k: v for k, v in structure}

	prefix = prefix or []
	res = format

	if isinstance(data, list):
		return ", ".join([formatString(format, x, structure, prefix, language, _rec=_rec + 1) for x in data])

	elif isinstance(data, str):
		return data

	elif not data:
		return res

	for key in data.keys():
		val = data[key]

		# Get structure if available
		struct = structure.get(key) if structure else None
		if isinstance(struct, list):
			struct = {k: v for k, v in struct}

		if isinstance(val, dict):
			if struct and ("$(%s)" % ".".join(prefix + [key])) in res:
				langs = struct.get("languages")
				if langs:
					if language and language in langs:
						val = val.get(language, "")
					else:
						val = ", ".join(val.values())

				else:
					continue

			else:
				res = formatString(res, val, structure, prefix + [key], language, _rec=_rec + 1)

		elif isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
			if struct and "dest" in val[0] and "rel" in val[0]:
				if "relskel" in struct and "format" in struct:
					format = struct["format"]
					struct = struct["relskel"]

				res = res.replace("$(%s)" % ".".join(prefix + [key]), ", ".join(
					[formatString(format, v, struct, [], language, _rec=_rec + 1) for v in val]))
			else:
				res = formatString(res, val[0], struct, prefix + [key], language, _rec=_rec + 1)

		elif isinstance(val, list):
			val = ", ".join(val)

		# Check for select-bones
		if isinstance(struct, dict) and "values" in struct and struct["values"]:
			vals = struct["values"]

			if isinstance(vals, list):
				vals = {k: v for k, v in vals}

			# NO elif!
			if isinstance(vals, dict) and isinstance(val, str):
				if val in vals:
					val = vals[val]

		res = res.replace("$(%s)" % (".".join(prefix + [key])), str(val))

	return res


class Spinner(object):
	run = False
	DELAY = 0.15

	def runner(self):
		chars = itertools.cycle([".  ", ".. ", "...", " ..", "  .", "   ",
								 "  .", " ..", "...", ".. ", ".  ", "   "])

		while self.run:
			sys.stdout.write(next(chars))
			sys.stdout.flush()
			time.sleep(self.DELAY)
			sys.stdout.write("\b" * 3)
			sys.stdout.flush()

	def __enter__(self):
		self.run = True
		threading.Thread(target=self.runner).start()
		return self

	def __exit__(self, exception, value, tb):
		self.run = False
		time.sleep(self.DELAY)
		return False


class ViurClient(object):

	def __init__(self, host: str, user: str, password: str):
		self.host = host.rstrip("/")
		self.user = user
		self.password = password

		self.session = requests.Session()

		self._doLogin()

	def _doLogin(self):
		self.request(
			"/vi/user/auth_userpassword/login",
			data={
				"name": self.user,
				"password": self.password,
			}, method="POST")

		assert self.request("/vi/user/view/self").ok, "Login was not successful"

	def request(self, path: str, data: Union[Dict, None] = None,
				params: Union[Dict, None] = None,
				method: str = "GET", addSkey: bool = True,
				*args, **kwargs) -> requests.Response:
		url = path
		if path.startswith("/"):
			url = "".join((self.host, path))

		if addSkey:
			if params is None:
				params = {}
			params["skey"] = self.getSkey()

		logger.debug("Do request: method=%r, url=%r, params=%r, data=%r",
					 method, url, params, data)
		return self.session.request(method, url, params, data, *args, **kwargs)

	def getSkey(self) -> str:
		return self.session.post(f"{self.host}/vi/skey").json()

	def list(self, module: str, params: Union[None, Dict] = None) -> Iterator[Dict[str, Any]]:
		if params is None:
			params = {}

		while True:
			response = self.request(f"/vi/{module}/list", params=params, addSkey=False)
			assert response.ok, (response.status_code, response.content)
			response = response.json()

			params["cursor"] = response["cursor"]

			if not response["skellist"]:
				break

			for skel in response["skellist"]:
				yield skel

	def view(self, module: str, key: str, *args, **kwargs) -> requests.Response:
		return self.request(f"/vi/{module}/view/{key}", addSkey=False, *args, **kwargs)

	def logout(self) -> bool:
		return self.request("/vi/user/logout").ok


class CsvExporter(object):
	EMPTY_VALUE = ""

	def __init__(self, viurClient: ViurClient):
		self.viurClient = viurClient

	def export(self, module: str, fileName: str = None, params: Dict = None,
			   columns: Optional[List] = None, onlyVisibleBones: bool = False) -> None:
		"""Export a VIUR-module to a CSV-file.

		:param module: The module name
		:param fileName: The filename of the csv
		:param params: Params for list request, e.g. filter or ordering
		:param columns: Export only these columns
		:param onlyVisibleBones: Export only visible bones
		"""
		if fileName is None:
			fileName = "export_%s_%s.csv" % (module, datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

		if params is None:
			params = {}
		assert isinstance(params, dict)
		assert columns is None or isinstance(columns, list)

		req = self.viurClient.view(module, "structure")

		assert req.ok, (req.status_code, req.reason)
		if req.url.endswith("/vi/s/main.html"):
			raise ValueError(f"Module {module!r} does not exists")

		rawStructure = req.json()["structure"]
		visibleColumns = [k for k, v in rawStructure
						  if (columns is None or k in columns) and (not onlyVisibleBones or v["visible"])]
		headers = self.getHeaders(rawStructure, visibleColumns)
		structure = {k: v for k, v in rawStructure if k in visibleColumns}

		with Spinner():
			with open(fileName, "w", newline="", encoding="utf-8") as csv_file:
				writer = csv.writer(csv_file)
				writer.writerow(headers.values())
				writer.writerows(map(functools.partial(self.renderRow, structure=structure),
									 self.viurClient.list(module, params)))

			logger.info("Export finished. File: %s", fileName)

	def getHeaders(self, structure: Dict[str, Dict], visibleColumns: List[str]) -> Dict[str, str]:
		headers = {}
		for boneName, boneStructure in structure:
			if boneName not in visibleColumns:
				continue

			if boneStructure.get("languages"):
				for lang in boneStructure["languages"]:
					headers[".".join((boneName, lang))] = f"{boneStructure['descr']} [{lang}]"
			else:
				headers[boneName] = boneStructure["descr"]

		return headers

	def renderRow(self, skel: Dict[str, Any], structure: Dict[str, Dict]) -> List[Any]:
		data = []

		for boneName, boneStructure in structure.items():
			if boneStructure.get("languages"):
				for lang in boneStructure["languages"]:
					data.append(self.renderBoneValue(boneName, skel[boneName], structure, lang))
			else:
				data.append(self.renderBoneValue(boneName, skel[boneName], structure))

		return data

	def renderBoneValue(self, boneName: str, boneValue: Any, structure: Dict[str, Dict],
						language: Optional[str] = None) -> Any:
		boneStructure = structure[boneName]
		boneType = boneStructure["type"]

		if language:
			boneValue = boneValue.get(language)

		if not boneValue:
			return self.EMPTY_VALUE

		if boneType == "str" or boneType.startswith("str."):
			if boneStructure["multiple"] or isinstance(boneValue, list):
				return ", ".join(boneValue)
			else:
				return boneValue

		if boneType == "select" or boneType.startswith("select."):
			if boneStructure["multiple"] or isinstance(boneValue, list):
				values = dict(boneStructure["values"])
				return ", ".join(values.get(x, x) for x in boneValue)
			else:
				return boneValue

		elif boneType == "treeitem.file":
			if not isinstance(boneValue, list):
				boneValue = [boneValue]
			res = []
			for fileRel in boneValue:
				res.append("%s (%s)" % (formatString(boneStructure["format"], boneValue, boneStructure),
										fileRel["dest"].get("servingurl")))
			return "\n".join(res)

		elif boneType == "numeric" or boneType.startswith("numeric."):
			return round(boneValue, boneStructure["precision"])

		elif boneType == "relational" or boneType.startswith("relational."):
			return formatString(boneStructure["format"], boneValue, boneStructure)

		else:
			return boneValue


if __name__ == "__main__":
	ap = argparse.ArgumentParser(description="ViUR CSV Exporter CLI")
	ap.add_argument("-c", "--connect", required=True, metavar="HOST", type=str,
					help="URL to ViUR application host")
	ap.add_argument("-u", "--username", type=str, required=True, help="Username")
	ap.add_argument("-p", "--password", type=str, required=True, help="Password")

	ap.add_argument("-V", "--verbose", action="store_true", help="Verbose mode")

	action = ap.add_mutually_exclusive_group(required=True)
	action.add_argument("-e", "--export", metavar="module", type=str,
						help="Export this module as csv")

	args = ap.parse_args()

	if args.verbose:
		logger.setLevel(logging.DEBUG)

	logger.debug("%s called with %r", sys.argv[0], args)

	vc = ViurClient(args.connect, args.username, args.password)

	try:
		if args.export:
			CsvExporter(vc).export(args.export, onlyVisibleBones=True)
	except KeyboardInterrupt:
		logger.info("KeyboardInterrupt. Export might be incomplete!")

	vc.logout()
