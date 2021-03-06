#!/usr/bin/env python
#
# savethemblobs.py
#   A simple script to grab all SHSH blobs from Apple that it's currently signing to save them locally and on Cydia server.
#   And now also grabs blobs already cached on Cydia servers to save them locally.
#
# Copyright (c) 2013 Neal <neal@ineal.me>
# 	Updated 2016 iApeiron
#		deprecated and obsolete APIs removed
#
# examples:
#   savethemblobs.py 1050808663311 iPhone3,1
#   savethemblobs.py 0x000000F4A913BD0F iPhone3,1 --overwrite
#   savethemblobs.py 1050808663311 n90ap --skip-cydia

import sys, os, argparse
import requests
import json

__version__ = '2.0'

USER_AGENT = 'savethemblobs/%s' % __version__

def firmwares_being_signed(device):
	url = 'http://api.ineal.me/tss/%s/' % (device)
	r = requests.get(url, headers={'User-Agent': USER_AGENT})
	return r.text
	
def firmwares(device):
	url = 'http://api.ineal.me/tss/%s/all' % (device)
	r = requests.get(url, headers={'User-Agent': USER_AGENT})
	return r.text
	
def beta_firmwares(device):
	url = 'http://api.ineal.me/tss/beta/%s/all' % (device)
	r = requests.get(url, headers={'User-Agent': USER_AGENT})
	return r.text

def tss_request_manifest(board, build, ecid, cpid=None, bdid=None):
	url = 'http://api.ineal.me/tss/manifest/%s/%s' % (board, build)
	r = requests.get(url, headers={'User-Agent': USER_AGENT})
	return r.text.replace('<string>$ECID$</string>', '<integer>%s</integer>' % (ecid))

def request_blobs_from_apple(board, build, ecid, cpid=None, bdid=None):
	url = 'http://gs.apple.com/TSS/controller?action=2'
	r = requests.post(url, headers={'User-Agent': USER_AGENT}, data=tss_request_manifest(board, build, ecid, cpid, bdid))
	if not r.status_code == requests.codes.ok:
		return { 'MESSAGE': 'TSS HTTP STATUS:', 'STATUS': r.status_code }
	return parse_tss_response(r.text)

def request_blobs_from_cydia(board, build, ecid, cpid=None, bdid=None):
	url = 'http://cydia.saurik.com/TSS/controller?action=2'
	r = requests.post(url, headers={'User-Agent': USER_AGENT}, data=tss_request_manifest(board, build, ecid, cpid, bdid))
	if not r.status_code == requests.codes.ok:
		return { 'MESSAGE': 'TSS HTTP STATUS:', 'STATUS': r.status_code }
	return parse_tss_response(r.text)

def submit_blobs_to_cydia(cpid, bdid, ecid, data):
	url = 'http://cydia.saurik.com/tss@home/api/store/%s/%s/%s' % (cpid, bdid, ecid)
	r = requests.post(url, headers={'User-Agent': USER_AGENT}, data=data)
	return r.status_code == requests.codes.ok

def write_to_file(file_path, data):
	f = open(file_path, 'w')
	f.write(data)
	f.close()

def parse_tss_response(response):
	ret = {}
	for v in response.split('&'):
		r = v.split('=',1)
		ret[r[0]] = r[1]
	return ret

def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('ecid', help='device ECID in int or hex (prefix hex with 0x)')
	parser.add_argument('device', help='device identifier/boardconfig (eg. iPhone3,1/n90ap)')
	parser.add_argument('--save-dir', help='local dir for saving blobs (default: ~/.shsh)', default=os.path.join(os.path.expanduser('~'), '.shsh'))
	parser.add_argument('--overwrite', help='overwrite any existing blobs', action='store_true')
	parser.add_argument('--overwrite-apple', help='overwrite any existing blobs (only from Apple)', action='store_true')
	parser.add_argument('--overwrite-cydia', help='overwrite any existing blobs (only from Cydia)', action='store_true')
	parser.add_argument('--no-submit-cydia', help='don\'t submit blobs to Cydia server', action='store_true')
	parser.add_argument('--skip-cydia', help='skip fetching blobs from Cydia server', action='store_true')
	parser.add_argument('--skip-cydia-beta', help='skip fetching beta blobs from Cydia server', action='store_true')
	return parser.parse_args()

def main(passedArgs = None):

	if passedArgs:
		args = passedArgs
	else:
		args = parse_args()

	ecid = int(args.ecid, 0)

	if not os.path.exists(args.save_dir):
		os.makedirs(args.save_dir)

	print 'Fetching firmwares Apple is currently signing for %s' % (args.device)
	d = firmwares_being_signed(args.device)
	if not d:
		print 'ERROR: No firmwares found! Invalid device.'
		return 1
	for device in json.loads(d).itervalues():
		board = device['board']
		model = device['model']
		cpid = device['cpid']
		bdid = device['bdid']
		for f in device['firmwares']:
			save_path = os.path.join(args.save_dir, '%s_%s_%s-%s.shsh' % (ecid, model, f['version'], f['build']))

			if not os.path.exists(save_path) or args.overwrite_apple or args.overwrite:
				print 'Requesting blobs from Apple for %s/%s' % (model, f['build'])
				r = request_blobs_from_apple(board, f['build'], ecid, cpid, bdid)

				if r['MESSAGE'] == 'SUCCESS':
					print 'Saving blobs to %s' % (save_path)
					write_to_file(save_path, r['REQUEST_STRING'])

					if not args.no_submit_cydia:
						print 'Submitting blobs to Cydia server'
						submit_blobs_to_cydia(cpid, bdid, ecid, r['REQUEST_STRING'])

				else:
					print 'Error receiving blobs: %s [%s]' % (r['MESSAGE'], r['STATUS'])

			else:
				print 'Skipping build %s; blobs already exist at %s' % (f['build'], save_path)

	if not args.skip_cydia:
		print 'Fetching blobs available on Cydia server'
		g = firmwares(args.device)
		if not g:
			print 'ERROR: No firmwares found! Invalid device.'
			return 1
		for device in json.loads(g).itervalues():
			board = device['board']
			model = device['model']
			cpid = device['cpid']
			bdid = device['bdid']
			for b in device['firmwares']:
				save_path = os.path.join(args.save_dir, '%s_%s_%s-%s.shsh' % (ecid, model, b['version'], b['build']))

				if not os.path.exists(save_path) or args.overwrite_cydia or args.overwrite:
					print 'Requesting blobs from Cydia for %s/%s' % (model, b['build'])
					r = request_blobs_from_cydia(board, b['build'], ecid, cpid, bdid)

					if r['MESSAGE'] == 'SUCCESS':
						print 'Saving blobs to %s' % (save_path)
						write_to_file(save_path, r['REQUEST_STRING'])

					else:
						print 'Error receiving blobs: %s [%s]' % (r['MESSAGE'], r['STATUS'])

				else:
					print 'Skipping build %s; blobs already exist at %s' % (b['build'], save_path)

	else:
		print 'Skipped fetching blobs from Cydia server'
				
	if not args.skip_cydia_beta:
		print 'Fetching beta blobs available on Cydia server'
		h = beta_firmwares(args.device)
		if not h:
			print 'ERROR: No firmwares found! Invalid device.'
			return 1
		for device in json.loads(h).itervalues():
			board = device['board']
			model = device['model']
			cpid = device['cpid']
			bdid = device['bdid']
			for c in device['firmwares']:
				save_path = os.path.join(args.save_dir, '%s_%s_%s-%s.shsh' % (ecid, model, c['version'], c['build']))

				if not os.path.exists(save_path) or args.overwrite_cydia or args.overwrite:
					print 'Requesting beta blobs from Cydia for %s/%s' % (model, c['build'])
					r = request_blobs_from_cydia(board, c['build'], ecid, cpid, bdid)

					if r['MESSAGE'] == 'SUCCESS':
						print 'Saving blobs to %s' % (save_path)
						write_to_file(save_path, r['REQUEST_STRING'])

					else:
						print 'Error receiving blobs: %s [%s]' % (r['MESSAGE'], r['STATUS'])

				else:
					print 'Skipping build %s; blobs already exist at %s' % (c['build'], save_path)

	else:
		print 'Skipped fetching beta blobs from Cydia server'

	return 0

if __name__ == '__main__':
	sys.exit(main())
