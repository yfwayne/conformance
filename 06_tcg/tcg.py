#
#  BSD LICENSE
#
#  Copyright (c) Crane Chu <cranechu@gmail.com>
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in
#      the documentation and/or other materials provided with the
#      distribution.
#    * Neither the name of Intel Corporation nor the names of its
#      contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# -*- coding: utf-8 -*-


import time
import pytest
import struct 
import logging

from nvme import *


comid = 0


class Command(Buffer):
    def start_anybody_adminsp_session(self):
        global comid
        self[:4] = struct.pack('>IHH', 0, comid, 0)
        self[0x38:] = struct.pack('>B', 0xF8)
        self[0x39:] = struct.pack('>BQ', 0xA8, 0xff)
        self[0x39+9:] = struct.pack('>BQ', 0xA8, 0xff02)
        self[0x39+9:] = struct.pack('>BQ', 0xA8, 0xff02)        
        
        

class Responce(Buffer):
    def level0_discovery(self):
        total_length, ver, _ = struct.unpack('>IIQ', self[:16])
        total_length += 4
        offset = 48
        while offset < total_length:
            feature, version, length = struct.unpack('>HBB', self[offset:offset+4])
            version >>= 4
            length += 4

            # parse discovery responce buffer
            logging.info((offset, feature, version, length))
            if feature == 0x303:
                # pyrite 2.0
                global comid
                comid, = struct.unpack('>H', self[offset+4:offset+6])
                
            offset += length
        assert offset == total_length
        logging.info(comid)
        

def test_pyrite_discovery0(nvme0):
    r = Responce()
    nvme0.security_receive(r, 1).waitdone()
    logging.info(r.dump(256))
    r.level0_discovery()

    
def test_start_anybody_session(nvme0):
    r = Responce()
    nvme0.security_receive(r, 1).waitdone()
    r.level0_discovery()
    
    c = Command()
    c.start_anybody_adminsp_session()
    logging.info(c.dump(256))
    
    

