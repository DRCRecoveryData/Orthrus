# Orthrus Carver
# Copyright (C) 2014 InFo-Lab
#
# This program is free software; you can redistribute it and/or modify it under the terms of the GNU
# Lesser General Public License as published by the Free Software Foundation; either version 2 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program; if not,
# write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

# coding=utf-8

import argparse
import datetime
import re
import os
import io

import FileValidators  # Ensure this module is compatible with Python 3

# A few constants:
DEBUG_BENCHMARK = True
CONST_BUILD = 18
CONST_VER = "0.2.3"
CONST_VERSTRING = "Version %s build %s" % (CONST_VER, CONST_BUILD)
CONST_YEARS = "2014"
CONST_BANNER = """
Orthrus carver
==============
InFo-Lab prototype %s
%s
""" % (CONST_YEARS, CONST_VERSTRING)

KILO = 1024
MEGA = 1024 * KILO
CONST_BLOCKSIZE = 10 * MEGA
CONST_FILESIZE = 5 * MEGA
CONST_SECTORSIZE = 512

# And now some variables:
headers_list = [
    b'\xff\xd8\xff',
    b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a',
    b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',
    b'GIF8',
]


def Carve(args):
    """
    Performs bifragment gap carving on the files referenced by args.

    :param args: dictionary with the arguments from the command line. Most important are the input
    file and the output directory.
    :return:
    """
    blocksize = CONST_BLOCKSIZE
    filesize = CONST_FILESIZE
    sectorsize = CONST_SECTORSIZE
    headers = list(map(re.escape, headers_list))
    rex_heads = re.compile(b"|".join(headers))
    
    validators = {
        b'\xff\xd8\xff': FileValidators.JPGValidator(),
        b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a': FileValidators.PNGValidator(),
        b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': FileValidators.MSOLEValidator(),
        b'GIF8': FileValidators.GIFValidator(),
    }
    
    extensions = {
        b'\xff\xd8\xff': ".jpg",
        b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a': ".png",
        b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': ".doc",
        b'GIF8': ".gif",
    }

    sois = {  
        b'\xff\xd8\xff': [
            b'\xff\xc0', b'\xff\xc1', b'\xff\xc2', b'\xff\xc3', b'\xff\xc4', b'\xff\xc5',
            b'\xff\xc6', b'\xff\xc7', b'\xff\xc8', b'\xffxc9', b'\xff\xca', b'\xff\xcb',
            b'\xff\xcc', b'\xff\xcd', b'\xff\xce', b'\xff\xcf', b'\xff\xd0', b'\xff\xd1',
            b'\xff\xd2', b'\xff\xd3', b'\xff\xd4', b'\xff\xd5', b'\xff\xd6', b'\xff\xd7',
            b'\xff\xd9', b'\xff\xda', b'\xff\xdb', b'\xff\xdc', b'\xff\xdd', b'\xff\xde',
            b'\xff\xdf'
        ],
        b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a': [b"PLTE", b"IDAT", b"IEND"],
        b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': [],
        b'GIF8': [b',', b';', b'\x21\xf9', b'\x21\x01', b'\x21\xff', b'\x21\xfe'],
    }
    
    rex_sois = {k: re.compile(b"|".join(map(re.escape, v))) for k, v in sois.items()}
    
    image = open(args.ipath, "rb")
    os.mkdir(args.opath)
    ostring = os.path.join(args.opath, "%08d%s")
    
    ext_number = 1
    block = image.read(blocksize)
    
    while block:
        print("-> %0.2f MB read" % (len(block) / MEGA))
        
        newblock = image.read(blocksize)
        bigblock = block + newblock
        match_results = rex_heads.finditer(block)
        
        for match in match_results:
            offset = match.start()
            head = match.group()
            val = validators[head]
            data = bigblock[offset: offset + filesize]
            print("Testing %s at %d..." % (head.hex(), offset))
            
            valid = val.Validate(data)
            extract = valid
            
            if not valid:
                lvb = val.GetStatus()[2]  # last valid byte
                gap_start = (lvb // sectorsize) + 1
                gap_end = (filesize // sectorsize) - 1
                
                if sois[head]:
                    rx = rex_sois[head]
                    end_match = rx.search(data[gap_start * sectorsize:])
                    if end_match:
                        gap_end = gap_start + (end_match.start() // sectorsize)
                        new_match = rx.search(data[(gap_end + 1) * sectorsize:])
                        if new_match:
                            gap_old = gap_end
                            gap_end = gap_start + (new_match.start() // sectorsize)
                            print("  got a new match, old(%d), new(%d)" % (gap_old, gap_end))
                    else:
                        continue
                else:
                    gap_end = (filesize // sectorsize) - 1
                
                print("  file not valid, trying gaps... (head: %s)" % (head.hex()))
                
                for gap_pos in range(gap_start, gap_end):
                    print("\r    gaps starting from %d..." % (gap_pos), end="")
                    gap_size_end = min(2048, gap_end - gap_pos)
                    
                    for gap_size in range(gap_size_end - 1, 0, -1):
                        pos1 = gap_pos * sectorsize
                        pos2 = (gap_pos + gap_size) * sectorsize
                        newdata = data[:pos1] + data[pos2:]
                        
                        if val.Validate(newdata):
                            extract = True
                            data = newdata
                            print("... validated with gap %d to %d!" % (gap_pos, gap_pos + gap_size))
                            break
                    if extract:
                        break
            
            if extract:
                extension = extensions[head]
                ext_size = val.GetStatus()[2]
                print("  extracted to %s, %d bytes" % (ostring % (ext_number, extension), ext_size))
                
                with open(ostring % (ext_number, extension), "wb") as fo:
                    fo.write(data[:ext_size])
                ext_number += 1
        
        block = newblock
    
    image.close()


def ArgParse():
    parser = argparse.ArgumentParser(description="orthrus: performs bifragment-gap-carving on a disk image.")
    parser.add_argument("ipath", help="Input path.")
    parser.add_argument("opath", help="Output path.")
    parser.add_argument("-l", dest="logfile", default="orthrus-log.md", help="Log file.")
    return parser.parse_args()


def main():
    print(CONST_BANNER)
    args = ArgParse()
    t1 = datetime.datetime.now()
    
    if os.path.isfile(args.ipath) and not os.path.exists(args.opath):
        Carve(args)
    else:
        print("ipath argument must be a valid file!")
        print("opath argument must be a non-existent directory!")
    
    dt = datetime.datetime.now() - t1
    if DEBUG_BENCHMARK:
        print("\nTime taken: %s" % dt)


if __name__ == "__main__":
    main()
