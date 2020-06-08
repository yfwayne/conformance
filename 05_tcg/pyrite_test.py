import pytest
import logging

from nvme import Buffer, TcgError, Qpair
import urllib.request

url = 'https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/richelieu-french-top20000.txt'


def test_pyrite_discovery0(nvme0):
    buf = Buffer(2048)
    nvme0.security_receive(buf, 1).waitdone()
    print(buf.dump(256))

    
def test_tcg_create(nvme0, tcg):
    tcg.take_ownership(b"liteon")


def test_tcg_password_hack_resist(nvme0, tcg):
    """ cannot crack with the password list """
    
    # verify set new password first
    tcg.set_new_passwd(b'liteon', b'liteon')

    for line in urllib.request.urlopen(url):
        with pytest.raises(TcgError):
            tcg.set_new_passwd(line.strip(), b'liteon')

    # authority locked out
    with pytest.raises(TcgError):
        tcg.set_new_passwd(b'liteon', b'liteon')

        
def test_tcg_lock_hack_resist(nvme0, tcg, subsystem):
    """ cannot crack with the password list """

    # power cycle to clear locked TCG state
    subsystem.power_cycle()
    nvme0.reset()
    
    # verify set new password first
    tcg.lock(b'liteon')

    for line in urllib.request.urlopen(url):
        with pytest.raises(TcgError):
            tcg.lock(line.strip())

    # authority locked out
    with pytest.raises(TcgError):
        tcg.lock(b'liteon')

        
def test_tcg_revert_hack_resist(nvme0, tcg, subsystem):
    """ cannot crack with the password list """
    
    # power cycle to clear locked TCG state
    subsystem.power_cycle()
    nvme0.reset()

    for line in urllib.request.urlopen(url):
        with pytest.raises(TcgError):
            tcg.revert_tper(line.strip())
            

def test_tcg_clear(nvme0, tcg, subsystem):
    # power cycle to clear locked TCG state
    subsystem.power_cycle()
    nvme0.reset()
    
    # revert need longer time
    nvme0.timeout = 100000
    tcg.revert_tper(b"liteon")
    nvme0.timeout = 10000

    # 2nd try, nothing to revert
    with pytest.raises(TcgError):
        tcg.revert_tper(b"liteon")


def test_tcg_revert_with_passwd(nvme0, tcg):
    tcg.take_ownership(b"liteon")
    
    with pytest.raises(TcgError):
        tcg.revert_tper(b"wrong_passwd")

    # revert need longer time
    nvme0.timeout = 100000
    tcg.revert_tper(b"liteon")
    nvme0.timeout = 10000


def test_tcg_lock_unlock(nvme0, nvme0n1, tcg, buf):
    tcg.take_ownership(b"liteon")
    
    q = Qpair(nvme0, 10)
    nvme0n1.read(q, buf, 0).waitdone()
    nvme0n1.write(q, buf, 0).waitdone()

    # lock both read and write
    tcg.lock(b'liteon')
    with pytest.warns(UserWarning, match="ERROR status: 02/86"):
        nvme0n1.read(q, buf, 0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/86"):
        nvme0n1.write(q, buf, 0).waitdone()

    # lock write
    tcg.lock(b'liteon', 1)
    nvme0n1.read(q, buf, 0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/86"):
        nvme0n1.write(q, buf, 0).waitdone()

    # unlock
    tcg.lock(b'liteon', 4)
    nvme0n1.read(q, buf, 0).waitdone()
    nvme0n1.write(q, buf, 0).waitdone()

    # revert need longer time
    nvme0.timeout = 100000
    tcg.revert_tper(b"liteon")
    nvme0.timeout = 10000
    

def test_tcg_pasword(nvme0, tcg):
    tcg.take_ownership(b"liteon")

    tcg.set_new_passwd(b'liteon', b'abcd1234')
    with pytest.raises(d.TcgError): # wrong password
        tcg.set_new_passwd(b'liteon', b'abcd1234')
    tcg.set_new_passwd(b'abcd1234', b'1')
    tcg.set_new_passwd(b'1', b'1'*32)
    with pytest.raises(d.TcgError): # too long password
        tcg.set_new_passwd(b'1'*32, b'1'*33)
    tcg.set_new_passwd(b'1'*32, b'ssstc')
    
    # revert need longer time
    nvme0.timeout = 100000
    tcg.revert_tper(b"ssstc")
    nvme0.timeout = 10000
    
