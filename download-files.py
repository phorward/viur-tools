import re, json, requests, sys, argparse, logging, os

root = logging.getLogger()
root.setLevel(logging.INFO)

class Exporter(requests.Session):
    def __init__(self, host, username=None, password=None, loginKey=None, render="json"):
        super().__init__()
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
        return super().get("/".join([self.host, self.render, url]), *args, **kwargs)

    def post(self, url, *args, **kwargs):
        if url.startswith("/"):
            url = url[1:]

        logging.debug("POST %s %s" % ("/".join([self.host, self.render, url]), kwargs))
        return super().post("/".join([self.host, self.render, url]), *args, **kwargs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="download-files.py - Download file trees from a ViUR system to local filesystem")

    ap.add_argument("target", type=str, help="The target folder to download to")

    ap.add_argument("-r", "--repo", type=str, help="Repository name", default="Files")
    ap.add_argument("-D", "--debug", action="store_true", help="Set debug log level")
    ap.add_argument("-c", "--connect", required=True, metavar="HOST", type=str, help="URL to ViUR application host")
    ap.add_argument("-u", "--username", type=str, help="Username")
    ap.add_argument("-p", "--password", type=str, help="Password")
    ap.add_argument("-l", "--loginkey", type=str, help="LoginKey")

    args = ap.parse_args()
    #print(args)

    downloader = Exporter(args.connect, args.username, args.password, args.loginkey, render="vi")

    # Retrieve key of root node
    rootNodes = downloader.get("/file/listRootNodes").json()
    rootNodeKey = None
    for rootNode in rootNodes:
        if rootNode["name"] == args.repo:
            rootNodeKey = rootNode["key"]
            break

    if rootNodeKey is None:
        logging.error("Cannot find repo named %r", args.repo)
        sys.exit(1)

    def download_folder(node_key, target_folder):
        logging.info("Folder %r", target_folder)
        os.makedirs(target_folder, exist_ok=True)

        # Files
        for file in downloader.get("/file/list/leaf/" + node_key).json()["skellist"]:
            if not file["dlkey"]:
                continue

            target_filename = os.path.join(target_folder, file["name"].replace("/", "-"))

            with downloader.get("/file/download/" + file["dlkey"], stream=True) as r:
                r.raise_for_status()
                with open(target_filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            logging.info("File %r", target_filename)

        # Folders
        for node in downloader.get("/file/list/node/" + node_key).json()["skellist"]:
            download_folder(node["key"], os.path.join(target_folder, node["name"].replace("/", "-")))


    download_folder(rootNodeKey, args.target)
