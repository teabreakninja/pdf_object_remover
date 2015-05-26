#!/usr/bin/env python

import argparse
import sys
import time
import mmap
import shutil
import os.path

"""
==============================================
Purpose: Removes 'www.it-ebooks.info' watermark from PDFs
Author:  Andy
==============================================
Using information from:
https://blog.idrsolutions.com/2010/09/grow-your-own-pdf-file-part-2-structure-of-a-pdf-file/
https://blog.idrsolutions.com/2011/05/understanding-the-pdf-file-format-%E2%80%93-pdf-xref-tables-explained/
https://stuff.mit.edu/afs/sipb/contrib/doc/specs/software/adobe/pdf/PDFReference16-v4.pdf

Notes:
[Header]:
	%PDF-x.x
	<%.....>
	
[Objects]:
	x x obj
	<<
	....
	>>
	endobj
	
[Xref]:
	xref
	0 271 <- number of entries
	0000000000 65535 f
	0000000015 00000 n <- [offset from start 10 bytes] [generation number 5 bytes] [in use (n) or not (f)1 byte] [two byte EOL]
	0000000102 00000 n

[Trailer]:
	trailer
	<<
	...
	>>
	
[Footer]:
	startxref
	xxxx <-offset of xref table (above)
	%%EOF
"""

def main(args):
	#if not args.files:
	#	print "file not found"
	#	sys.exit()

	# check the file exists
	if not os.path.isfile(args.files[0]):
		print "[-] ERROR: File '{}' does not exist".format(args.files[0])
		sys.exit()
	
	# make a copy of the file
	print "[*] Making a copy of {0}".format(args.files[0])
	editable_file = args.files[0].replace(".pdf", "_fixed.pdf")
	shutil.copyfile(args.files[0], editable_file)
	filepointer = open(editable_file, "r+b")
	print "[*] Making all changes to {0}".format(editable_file)
	
	fp = mmap.mmap(filepointer.fileno(), 0)
	
	# PDF version number
	pdf_version =  fp.readline().replace('%PDF-','').rstrip()
	print "[*] File has PDF version '{}'".format(pdf_version)

	# seek to end
	fp.seek(0,2)
	
	# backup, check for '%%EOF'
	fp.seek(-6,1)
	check = fp.readline().replace('\n','')
	print "[*] Checking for %%EOF...",
	if check == "%%EOF":
		print " FOUND"
	else:
		print " ERROR, found '{0}'".format(check)
		sys.exit()

	tmp = ''
	# backup until find startxref
	while tmp[0:9] != 'startxref':
		fp.seek(-2,1)
		tmp = fp.read(1) + tmp

	print "[+] Looking for string 'startxref' found {0} at {1}".format(tmp[0:9], fp.tell()-1)

	# check for multiple xref sections
	startxref_pos = 0
	startxref_list = []
	while True:
		tmp = fp.find('startxref',startxref_pos+1)
		if tmp == -1:
			break;
		else:
			print "[+] Found startxref at {0}".format(tmp)
			startxref_pos = tmp
			startxref_list.append(tmp)

	xref_offset = startxref_pos
	#sys.exit()

	#tmp = ''
	#while fp.tell() != 0:
	#	fp.seek(-2,1)
	#	print '{0}\r'.format(fp.tell()),
	#	tmp = fp.read(1) + tmp
	#	if tmp[0:9] == 'startxref':
	#		print "[!] startxref found at {}".format(fp.tell())
	
	for xref_offset in startxref_list:
		fp.seek(xref_offset,0)
		# readline twice (once for startxref) to get the offset of xref
		fp.readline()
		xref_offset = (int)(fp.readline().rstrip())
		print "[+] Reported startxref offset: {0}".format(xref_offset)
		
		# seek to the start of xref
		fp.seek(xref_offset, 0)

		# ensure the line is the 'xref' tag
		xref_string = fp.readline().rstrip()
		if (xref_string != 'xref'):
			print "[-] Error, xref not found at offset, found '{0}'".format(xref_string)
			sys.exit()
			
		print "[+] Reading xref table..."
		
		# next line is number of objects
		object_count = fp.readline().split()[1]
		
		# readline until string is 'trailer'
		pdf_objects = []
		line = ''
		while (line != 'trailer'):
			xref_current = fp.tell()
			line = fp.readline().rstrip()
			if line == 'trailer':
				break;
				
			# test if the cross reference is single or double subsection
			try:
				[offset, version, inuse] = line.split()
			except:
				print "[-] Error reading line:"
				print "[-] Expecting [offset, version, inuse], found '{}'".format(line)
				#sys.exit()
				continue
				
			pdf_objects.append([offset, inuse, xref_current])
			
		print "[+] Done, xref object count: {0}, actual count: {1}".format(object_count, len(pdf_objects))
		
		found_objects = 0
		byte_count = 0
		# read each object
		for idx, obj in enumerate(pdf_objects):
			offset,inuse,xref_pointer = obj
			
			if obj[1] == 'f':
				print "[+] Object {0} not in use, skipping".format(idx)
				continue
			#else:
			#	print "Reading object {0} at offset {1}".format(idx, offset)
			#	pass
				
			fp.seek(int(offset), 0)
			obj_string = ''
			sys.stdout.write('.')
			sys.stdout.flush()
			
			# readline until endobj is found
			while True:
				tmp = fp.readline()
				obj_string += tmp

				if tmp.rstrip() == 'endobj':
					break
			
			# check for our string!
			if 'it-ebooks' in obj_string:
				#print "Found string in object #{0}".format(idx)
				sys.stdout.write('x')
				found_objects += 1
				byte_count += len(obj_string)
				# mark the object as 'not in use' (f)
				# go to xref position, readline, go back three bytes ('n' and two-byte-eol) and write an 'f'
				fp.seek(int(xref_pointer),0)
				#fp.readline()
				#fp.seek(-3,1)
				#fp.write_byte("f")
				fp.write("0000000000 65535 f \n")
		print ""

	print "\n[+] Finished"
	print "[*] Matching object count: {0}".format(found_objects)
	print "[*] Potential saving of {0} bytes".format(byte_count)
	
	fp.close()
	filepointer.close()
	print "[*] Changes written to {0}".format(editable_file)
	
if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("-f", "--files",
		help="One or more PDF files to remove it-ebook's watermarks.",
		nargs="*", required=True)

	parser.add_argument("--no-backup",
		help="Disables the creating of backups for the files which"+\
		 " are being processed. ",
		action="store_true")

	parser.add_argument("-v", "--verbose", action="store_true")
  
	args = parser.parse_args()

	main(args)

	
