# conformance

download, test, report:
```shell
cd pynvme
git clone https://github.com/pynvme/conformance scritps/conformance
make test TESTS=scripts/conformance pciaddr=0000:01:00.0
less test_0000:01:00.0.log
```
