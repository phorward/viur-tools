import sqlite3
import pickle
import urllib2
from urllib import quote_plus
from time import time, sleep
import pickle, json, random, mimetypes, string, sys, os
import argparse

parser = argparse.ArgumentParser(description='Copies the complete Blob-Store from the given application to the destination Application.')
parser.add_argument('--srcappid', type=str, help='Appspot-ID of the src Application.', required=True, dest="srcappid")
parser.add_argument('--srckey', type=str, help='Download-Key for the Application.', required=True, dest="srckey")
parser.add_argument('--dstappid', type=str, help='Appspot-ID of the dst Application.', required=True, dest="dstappid")
parser.add_argument('--dstkey', type=str, help='Download-Key for the dst Application.', required=True, dest="dstkey")
parser.add_argument('--localblobdb', type=str, help='Hold and use local hasblob DB to reduce amount of hasblob calls')
parser.add_argument('--override', type=bool, default=False, help='Override blobs even if they already exists')

args = parser.parse_args()


class NetworkService( object ):
	baseURL = None
	def __init__( self,  baseURL ):
		super( NetworkService, self ).__init__()
		self.baseURL = baseURL
		cp = urllib2.HTTPCookieProcessor()
		self.opener = urllib2.build_opener( cp )
		urllib2.install_opener( self.opener )

	@staticmethod
	def genReqStr( params ):
		boundary_str = "---"+''.join( [ random.choice(string.ascii_lowercase+string.ascii_uppercase + string.digits) for x in range(13) ] )
		boundary = boundary_str.encode("UTF-8")
		res = b'Content-Type: multipart/mixed; boundary="'+boundary+b'"\nMIME-Version: 1.0\n'
		res += b'\n--'+boundary
		for(key, value) in list(params.items()):
			if all( [x in dir( value ) for x in ["name", "read"] ] ): #File

				if getattr(value, "content_type") and value.content_type:
					type = value.content_type
				else:
					try:
						(type, encoding) = mimetypes.guess_type( value.name.decode( sys.getfilesystemencoding() ), strict=False )
						type = type or b"application/octet-stream"
					except:
						type = b"application/octet-stream"

				res += b'\nContent-Type: '+type.encode("UTF-8")+b'\nMIME-Version: 1.0\nContent-Disposition: form-data; name="'+key.encode("UTF-8")+b'"; filename="'+os.path.basename(value.name).decode(sys.getfilesystemencoding()).encode("UTF-8")+b'"\n\n'
				res += value.read()
				res += b'\n--'+boundary
			elif isinstance( value, list ):
				for val in value:
					res += b'\nContent-Type: application/octet-stream\nMIME-Version: 1.0\nContent-Disposition: form-data; name="'+key.encode("UTF-8")+b'"\n\n'
					if isinstance( val, unicode ):
						res += val.encode("UTF-8")
					else:
						res += str(val)
					res += b'\n--'+boundary
			else:
				res += b'\nContent-Type: application/octet-stream\nMIME-Version: 1.0\nContent-Disposition: form-data; name="'+key.encode("UTF-8")+b'"\n\n'
				if isinstance( value, unicode ):
					res += unicode( value ).encode("UTF-8")
				else:
					res += str( value )
				res += b'\n--'+boundary
		res += b'--\n'
		return( res, boundary )

	def request( self, url, params=None, secure=False, extraHeaders=None, noParse=False ):
		def rWrap( self, url, params=None, secure=False, extraHeaders=None, noParse=False):
			if secure:
				skey = json.loads( urllib2.urlopen( self.baseURL+ "/skey" ).read() )
				if params is None or isinstance(params,bytes):
					if "?" in url:
						url += "&skey="+skey
					else:
						url += "?skey="+skey
				else:
					params["skey"] = skey
			if not url.lower().startswith("https://") and not url.lower().startswith("http://"):
				url = self.baseURL+url
			if isinstance( params,  dict ):
				res, boundary = self.genReqStr( params )
				r = urllib2.Request((url).encode("UTF-8"), res, headers={b"Content-Type": b'multipart/form-data; boundary='+boundary+b'; charset=utf-8'})
				req = urllib2.urlopen( r )
			else:
				req = urllib2.urlopen( url )
			if noParse:
				return( req.read() )
			else:
				return( pickle.loads( req.read().decode("HEX") ) )
		for x in range(0,4):
			try:
				return( rWrap( self, url, params, secure, extraHeaders, noParse ) )
			except Exception as e:
				if x<3:
					print("Error during network request:", e, "Retrying in 60 seconds"  )
					sleep( 60 )
				else:
					print("Fatal error in network request, exiting")
					print("Failed request was")
					print( url, params, secure, extraHeaders, noParse)
					raise

class fwrap(object):
	def __init__(self, blob, name="", content_type=""):
		super( fwrap, self ).__init__()
		self._blob = blob
		self.name = name.encode(sys.getfilesystemencoding())
		self.content_type = content_type

	def read(self, *args, **kwargs):
		return( self._blob )

def haveBlob( blobKey ):
	global dstNetworkService, dstBackupKey, blobdbfile, knownblobs

	if blobKey in knownblobs:
		return True

	answ = dstNetworkService.request(
			"/dbtransfer/hasblob/%s/%s" % (blobKey,dstBackupKey), noParse=True)

	answ = answ.lower() == "true"

	if answ:
		knownblobs.append(blobKey)

		if blobdbfile:
			blobdbfile.write("%s\n" % blobKey)
		
	return answ

def fetchBlob( blobKey ):
	global srcNetworkService
	return( srcNetworkService.request("/file/download/%s" %blobKey, noParse=True))

def storeBlob( blobKey, blob, content_type = ""):
	global dstNetworkService, dstBackupKey

	#print(blobKey)

	ulurl = dstNetworkService.request("/dbtransfer/getUploadURL",{"key":dstBackupKey}, noParse=True ).decode("UTF-8")
	#print("-------")
	#print( ulurl )

	data = dstNetworkService.request(ulurl, {   "file": fwrap(blob,"file1", content_type),
	                                            "key":dstBackupKey,
	                                            "oldkey":blobKey},
	                                 noParse=True ).decode("UTF-8")
	data = json.loads(data)
	if data["action"] == "addSuccess":
		return( data["values"][0]["dlkey"])

if not "localhost" in args.srcappid:
	viurSrcHost = "https://%s.appspot.com/" % args.srcappid
else:
	viurSrcHost = "http://%s/" % args.srcappid

if not "localhost" in args.dstappid:
	viurDstHost = "https://%s.appspot.com/" % args.dstappid
else:
	viurDstHost = "http://%s/" % args.dstappid

#viurHost = "http://127.0.0.1:8080/"
srcBackupKey = args.srckey
dstBackupKey = args.dstkey
localblobdb = args.localblobdb
override = args.override
knownblobs = []
blobdbfile = None

print("Source Host: %s" % viurSrcHost)
print("Destination Host: %s" % viurDstHost)
if localblobdb:
	print("Local blob DB: %s" % localblobdb)
	try:
		blobdbfile = open(localblobdb, "r+")
		knownblobs = [x.strip() for x in blobdbfile.readlines()]

		print("%d entries in local blob DB found!" % len(knownblobs))
	except:
		blobdbfile = open(localblobdb, "w")

srcNetworkService = NetworkService(viurSrcHost)
dstNetworkService = NetworkService(viurDstHost)

#Fetch blobs
res = srcNetworkService.request("/dbtransfer/exportBlob2",
			{"key": srcBackupKey})

numBlobs = 0
while res["values"]:
	numBlobs += len( res["values"] )
	print("Got a total of %s blobs so far" % numBlobs )
	newBlobs = 0
	for r in res["values"]:
		if override or not haveBlob( r["key"] ):
			print("Fetching new blobkey %s" % r["key"] )
			if r["content_type"] == "application/pdf":
				print("- Ignoring: %r" % r["content_type"])
				continue

			storeBlob( r["key"], fetchBlob( r["key"] ), r["content_type"] )
			newBlobs += 1
	print("%s of the last batch of %s where new" % (newBlobs, len(res["values"])))
	res = srcNetworkService.request("/dbtransfer/exportBlob2", {"cursor":res["cursor"], "key": srcBackupKey})

print("Finished copying %d files" % numBlobs)
