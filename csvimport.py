# -*- coding: utf-8 -*-
import re, json, csv, requests, sys, codecs, argparse, logging, os, logics

root = logging.getLogger()
root.setLevel(logging.INFO)

sys.stdout = codecs.getwriter("utf8")(sys.stdout)

class Importer(requests.Session):
	def __init__(self, host, username=None, password=None, loginKey=None, render="json"):
		super(Importer, self).__init__()

		self.render = render

		self.host = host

		self.username = username
		self.password = password
		self.loginKey = loginKey

		assert (self.username and self.password) or self.loginKey

		if not self.login():
			raise IOError("Unable to logon to '%s'" % self.host)

	def login(self):
		if self.username and self.password:
			answ = self.post(
				"/user/auth_userpassword/login",
				data={
					"name": self.username,
					"password": self.password,
					"skey": self.skey()
				},
				timeout=30)
		else:
			answ = self.post(
				"/user/auth_loginkey/login",
				data={
					"key": self.loginKey,
					"skey": self.skey()
				},
				timeout=30)

		if not answ.status_code == 200:
			logging.error("Unable to logon to '%s'" % self.host)
			return False

		res = re.search(r"JSON\(\((.*)\)\)", answ.text)

		if res:
			res = json.loads(res.group(1))
		else:
			res = answ.json()

		assert res == "OKAY"

		logging.debug("HELLO %s!" % self.host)
		return True

	def logout(self):
		return self.get("/user/logout", params={"skey": self.skey()}, timeout=10).json()

	def skey(self):
		return self.get("/skey", timeout=15).json()

	def get(self, url, *args, **kwargs):
		if url.startswith("/"):
			url = url[1:]

		logging.debug("GET  %s %s" % ("/".join([self.host, self.render, url]), kwargs))
		return super(Importer, self).get("/".join([self.host, self.render, url]), *args, **kwargs)

	def post(self, url, *args, **kwargs):
		if url.startswith("/"):
			url = url[1:]

		logging.debug("POST %s %s" % ("/".join([self.host, self.render, url]), kwargs))
		return super(Importer, self).post("/".join([self.host, self.render, url]), *args, **kwargs)

	def list(self, module, *args, **kwargs):
		req = self.get("/%s/list" % module, params=kwargs, timeout=60)

		if not req.status_code == 200:
			logging.error("Error %d, unable to fetch items" % req.status_code)
			return None

		return req.json()

	def logic_lookup(self, module, field, value, result = "key"):
		ret = self.list(module, **{field: value, "amount": 1})

		if ret["skellist"]:
			return ret["skellist"][0][result]

		return None


if __name__ == "__main__":
	ap = argparse.ArgumentParser(description="csv2viur - Generic CSV importer for ViUR.")

	ap.add_argument("filename", type=str, help="The CSV-File to be imported")

	ap.add_argument("-D", "--debug", action="store_true", help="Set debug log level")
	ap.add_argument("-d", "--delimiter", default=";", type=str, help="Value delimiter in CSV-file")
	ap.add_argument("-m", "--module", type=str, help="Module to import to (is retrieved by filename else)")
	ap.add_argument("-U", "--update", action="store_true", dest="updateEntry", help="Update entries which already exist")
	ap.add_argument("-k", "--key-column", metavar="key-column", dest="keyColumn", type=str, help="Name of the key column")
	ap.add_argument("-c", "--connect", required=True, metavar="HOST", type=str, help="URL to ViUR application host")
	ap.add_argument("-u", "--username", type=str, help="Username")
	ap.add_argument("-p", "--password", type=str, help="Password")
	ap.add_argument("-l", "--loginkey", type=str, help="LoginKey")
	ap.add_argument("-e", "--expression", metavar=("column", "expression"), action="append", nargs=2, type=str,
					help="Define additional field expression")

	args = ap.parse_args()
	#print(args)

	imp = Importer(args.connect, args.username, args.password, args.loginkey, render="vi")

	if not args.module:
		args.module = os.path.splitext(args.filename)[0]

	reader = csv.DictReader(open(args.filename, "rb"), delimiter=args.delimiter)

	added = 0
	updated = 0

	vil = logics.Interpreter()
	#vil.functions["lookup"] = logics.Function(imp.logic_lookup, None)
	#vil.functions["csvlookup"] = logics.Function(imp.logic_lookup, None)

	rules = {}

	for row in reader:
		key = None

		if args.expression:
			for i, expr in enumerate(args.expression):
				#print(expr[0], expr[1], row.get(expr[0]))
				field = expr[0]

				if field not in rules:
					rules[(field, i)] = vil.compile(expr[1])

				row[field] = vil.execute(rules[(field, i)], row)
				#print("=", row[field])

		if args.keyColumn:
			if args.keyColumn not in reader.fieldnames:
				logging.error("Key field '%s' does not exist in %s." % (args.keyColumn, args.filename))
				sys.exit(1)

			answ = imp.list(args.module, **{args.keyColumn: row[args.keyColumn]})

			if len(answ["skellist"]) == 1:
				key = answ["skellist"][0]["key"]

				if not args.updateEntry:
					logging.info("Entry %s exists and will not be updated." % row[args.keyColumn])
					continue

			elif len(answ["skellist"]) > 1:
				logging.error("Multiple matches on '%s'? IMPOSSIBLE!!" % row[args.keyColumn])
				continue

		row["skey"] = imp.skey()

		if key:
			row["key"] = key
			answ = imp.post(args.module + "/edit", data=row).json()

			if answ["action"] != "editSuccess":
				logging.error(
					"%s/edit/%s failed with errors: %s", args.module, key,
					", ".join([("%s=%s: %s" % (bone, answ["values"][bone], struct["error"]))
							   for bone, struct in answ["structure"] if struct["error"]])
				)
				continue

			logging.info("%r updated successfully", key)
			updated += 1
		else:
			answ = imp.post(args.module + "/add", data=row).json()

			if answ["action"] == "addSuccess":
				logging.info("%r created successfully", answ["values"]["key"])
				added += 1

		#break

	logging.info("%d added, %d updated", added, updated)
