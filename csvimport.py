# -*- coding: utf-8 -*-
# Import customers:
#   python csvimport.py -c http://localhost:8080 -u admin@phorward.appspot.com -p XucPQU9IHMlxT -m customer -d "#" -r lastname "company if not lastname else lastname" -r firstname "' '.join(lastname.replace(lastname.split()[-1], '').split())" -r lastname "lastname.split()[-1]" -r no_support "'1' if no_support == '0' else '0'" -r vip "'1' if vip == '0' else '0'" -r country "country.lower()" -r email "email.strip()" -k customer_id customers.csv

import csv, requests, sys, codecs, argparse, logging, os, logics

#root = logging.getLogger()
#root.setLevel(logging.DEBUG)

sys.stdout = codecs.getwriter("utf8")(sys.stdout)

class Importer(requests.Session):
	def __init__(self, host, username, password, render = "json"):
		super(Importer, self).__init__()

		self.render = render

		self.host = host
		self.username = username
		self.password = password

		if not self.login():
			raise IOError("Unable to logon to '%s'" % self.host)

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

	def login(self):
		answ = self.post("/user/auth_userpassword/login",
		                 data={"name": self.username,
		                       "password": self.password,
		                       "skey": self.skey()},
		                 timeout=30)

		if not (answ.status_code == 200 and answ.json() == "OKAY"):
			logging.error("Unable to logon to '%s'" % self.host)
			return False

		logging.debug("HELLO %s!" % self.host)
		return True

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

	ap.add_argument("-d", "--delimiter", default=";", type=str, help="Value delimiter in CSV-file")
	ap.add_argument("-m", "--module", type=str, help="Module to import to (is retrieved by filename else)")
	ap.add_argument("-k", "--key", type=str, help="Check for key column")
	ap.add_argument("-c", "--connect", required=True, metavar="HOST", type=str,
	                    help="URL to ViUR application host")
	ap.add_argument("-u", "--username", required=True, type=str, help="Username")
	ap.add_argument("-p", "--password", required=True, type=str, help="Password")
	ap.add_argument("-t", "--translate", metavar=("column", "value", "replace"),
	                action="append", nargs=3, type=str, help="Additional field translations")
	ap.add_argument("-r", "--rule", metavar=("column", "expression"),
	                action="append", nargs=2, type=str, help="Additional field rule")
	ap.add_argument("-U", "--allow-update", dest="update", action="store_true",
	                    help="Allow dataset updating.")

	args = ap.parse_args()
	#print(args)

	imp = Importer(args.connect, args.username, args.password, render="admin")

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

		if args.key:
			if args.key not in reader.fieldnames:
				logging.error("Key field '%s' does not exist in %s." % (args.key, args.filename))
				sys.exit(1)

			answ = imp.list(args.module, **{args.key: row[args.key]})

			if len(answ["skellist"]) == 1:
				key = answ["skellist"][0]["key"]

				if not args.update: #fixme: no update option
					logging.info("Entry %s exists and will not be updated." % row[args.key])
					continue

			elif len(answ["skellist"]) > 1:
				logging.error("Multiple matches on '%s'? IMPOSSIBLE!!" % row[args.key])
				continue

		if args.rule:
			for i, rule in enumerate(args.rule):
				#print(rule[0], rule[1], row.get(rule[0]))
				field = rule[0]

				if field not in rules:
					rules[(field, i)] = vil.compile(rule[1])

				row[field] = vil.execute(rules[(field, i)], row)
				#print("=", row[field])

		print(row)
		row["skey"] = imp.skey()

		if key:
			row["key"] = key
			answ = imp.post(args.module + "/edit", data=row).json()

			if answ["action"] == "editSuccess":
				updated += 1
		else:
			answ = imp.post(args.module + "/add", data=row).json()

			if answ["action"] == "addSuccess":
				added += 1

		#break

	print("%d added, %d updated" % (added, updated))
