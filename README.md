[![Build Status](https://travis-ci.org/ihucos/plash-svg?branch=stable1)](https://travis-ci.org/ihucos/plash)

```
$ #
$ # Install 
$ #
$ pip3 install git+https://github.com/ihucos/plash.git
$
$ #
$ # Examples 
$ #
$ plash-build --os ubuntu --run 'touch /file'
Container not found, trying to pull it
[0%|10%|20%|30%|40%|50%|60%|70%|80%|90%|100%]
--> touch /file
--:
a64
$ plash-run a64 file /file
/file: empty
$ plash-build --os ubuntu --run 'touch /file' --layer --run 'touch /file2'
--> touch /file2
--:
858









```
