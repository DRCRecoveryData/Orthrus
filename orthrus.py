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
import io
import datetime
import os
import re
from JPGValidator import JPGValidator  # Directly import JPGValidator

# Constants
DEBUG_BENCHMARK = True
CONST_BUILD = 19
CONST_VER = "0.2.4"
CONST_VERSTRING = f"Version {CONST_VER} build {CONST_BUILD}"
CONST_YEARS = "2025"
CONST_BANNER = f"""
Orthrus carver
==============
InFo-Lab prototype {CONST_YEARS}
{CONST_VERSTRING}
"""

KILO = 1024
MEGA = 1024 * KILO
CONST_BLOCKSIZE = 10 * MEGA
CONST_FILESIZE = 5 * MEGA
CONST_SECTORSIZE = 512

# Headers for JPG only
headers_list = [
    b'\xff\xd8\xff'  # JPG
]

def Carve(args):
    blocksize = CONST_BLOCKSIZE
    filesize = CONST_FILESIZE
    sectorsize = CONST_SECTORSIZE
    headers = [re.escape(h) for h in headers_list]
    rex_heads = re.compile(b"|".join(headers))

    validators = {
        b'\xff\xd8\xff': JPGValidator()  # Use JPGValidator directly
    }
    
    extensions = {
        b'\xff\xd8\xff': ".jpg"
    }
    
    sois = {
        b'\xff\xd8\xff': [
            b'\xff\xc0', b'\xff\xc1', b'\xff\xc2', b'\xff\xc3', b'\xff\xc4', b'\xff\xc5',
            b'\xff\xc6', b'\xff\xc7', b'\xff\xc8', b'\xff\xc9', b'\xff\xca', b'\xff\xcb',
            b'\xff\xcc', b'\xff\xcd', b'\xff\xce', b'\xff\xcf', b'\xff\xd0', b'\xff\xd1',
            b'\xff\xd2', b'\xff\xd3', b'\xff\xd4', b'\xff\xd5', b'\xff\xd6', b'\xff\xd7',
            b'\xff\xd9', b'\xff\xda', b'\xff\xdb', b'\xff\xdc', b'\xff\xdd', b'\xff\xde',
            b'\xff\xdf', b'\xffxe0', b'\xff\xe1', b'\xff\xe2', b'\xff\xe3', b'\xff\xe4',
            b'\xff\xe5', b'\xff\xe6', b'\xff\xe7', b'\xffxe8', b'\xff\xe9', b'\xff\xea',
            b'\xffxeb', b'\xff\xec', b'\xff\xed', b'\xff\xee', b'\xffxef', b'\xffxf0',
            b'\xff\xf1', b'\xff\xf2', b'\xff\xf3', b'\xffxf4', b'\xff\xf5', b'\xff\xf6',
            b'\xffxf7', b'\xff\xf8', b'\xffxf9', b'\xff\xfa', b'\xffxfb', b'\xff\xfc',
            b'\xffxfd', b'\xff\xfe'
        ]
    }
    
    rex_sois = {k: re.compile(b"|".join(map(re.escape, v))) for k, v in sois.items()}

    with open(args.ipath, "rb") as image:
        os.makedirs(args.opath, exist_ok=True)
        ostring = os.path.join(args.opath, "{:08d}{}")
        ext_number = 1
        block = image.read(blocksize)

        while block:
            print(f"-> {len(block) / MEGA:.2f} MB read")
            newblock = image.read(blocksize)
            bigblock = block + newblock
            match_results = rex_heads.finditer(block)

            for match in match_results:
                offset = match.start()
                head = match.group()
                val = validators[head]
                data = bigblock[offset: offset + filesize]

                print(f"Testing {head.hex()} at {offset}...")
                valid = val.Validate(data)

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
                                gap_end = gap_start + (new_match.start() // sectorsize)
                                print(f"  got a new match, gap end adjusted to {gap_end}")
                        else:
                            continue

                    print(f"  file not valid, trying gaps... (head: {head.hex()})")
                    for gap_pos in range(gap_start, gap_end):
                        print(f"\r    gaps starting from {gap_pos}...", end="", flush=True)
                        gap_size_end = min(2048, gap_end - gap_pos)

                        for gap_size in range(gap_size_end - 1, 0, -1):
                            pos1 = gap_pos * sectorsize
                            pos2 = (gap_pos + gap_size) * sectorsize
                            newdata = data[:pos1] + data[pos2:]

                            if val.Validate(newdata):
                                data = newdata
                                print(f"... validated with gap {gap_pos} to {gap_pos + gap_size}!")
                                break

                        if val.Validate(data):
                            break

                if val.Validate(data):
                    extension = extensions[head]
                    ext_size = val.GetStatus()[2]
                    output_path = ostring.format(ext_number, extension)
                    print(f"  extracted to {output_path}, {ext_size} bytes")

                    with open(output_path, "wb") as fo:
                        fo.write(data[:ext_size])

                    ext_number += 1

            block = newblock

def ArgParse():
    """
    Parses the command line arguments
    :return: argparse dictionary
    """
    parser = argparse.ArgumentParser(
        description="orthrus: performs bifragment-gap-carving on a disk image.")
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
        print(f"\nTime taken: {dt}")

if __name__ == "__main__":
    main()
