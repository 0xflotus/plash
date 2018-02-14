package main

import "syscall"
import "bytes"
import "os"
import "io/ioutil"
import "os/exec"
import "fmt"
import "strconv"
import "path/filepath"
import "path"
import "runtime"

func isint(val string) bool {
	if _, err := strconv.Atoi(val); err == nil {
		return true
	}
	return false
}

func call(name string, arg ...string) {
	err := exec.Command(name, arg...).Run()
	if err != nil {
		panic(err)
	}
}

func check(err error) {
        if err != nil { panic(err) }
}

func pathExists(path string) (bool) {
        _, err := os.Stat(path)
        if err == nil { return true }
        if os.IsNotExist(err) { return false }
        panic(err)
}

func main() {

	container := os.Args[1]
	if !isint(container) {
		panic("argument must be an container, which is an integer")
	}

        // Think three times before removing this line.
        // without it, chroot could be executed in a thread that still is root.
        // That would be a privilege escalation
        runtime.LockOSThread() 

        callerUid := syscall.Getuid()
        err := syscall.Setreuid(0, 0); check(err)

        // the mountpoint to chroot into
        bootId, err := ioutil.ReadFile("/proc/sys/kernel/random/boot_id"); check(err)
        plashId, err := ioutil.ReadFile("/var/lib/plash/id"); check(err) // if err, plash was not initialized yet
        finalMountpoint := fmt.Sprintf("/var/run/plash-run-suid-%s-%s-%d", bootId, plashId, container)

        //
        // populate mountpoint, if not done yet
        //
        if ! pathExists(finalMountpoint){
                
                mountpoint, err := ioutil.TempDir("/var/tmp", "plash-run-suid-mountpoint-"); check(err)
                topLayer, err := os.Readlink("/var/lib/plash/index/" + container); check(err)

                // generate the overlay options for mount
                var buffer bytes.Buffer
                buffer.WriteString("lowerdir=")
                first := true
                for {
                        cont := filepath.Base(topLayer)
                        topLayer = filepath.Dir(topLayer)
                        if !isint(cont) {
                                break
                        }
                        if !first {
                                buffer.WriteString(":")
                        }
                        first = false
                        buffer.WriteString("/var/lib/plash/index/")
                        buffer.WriteString(cont)
                        buffer.WriteString("/_data/root")
                }
                buffer.WriteString(",nosuid")
                overlayOpts := buffer.String()

                // mount directories
                call("mount", "-t", "overlay", "overlay", "-o", overlayOpts, mountpoint)
                call("mount", "-t", "proc", "-o", "rw,nosuid,nodev,noexec,relatime",
                        "/proc", path.Join(mountpoint, "/proc"))
                call("mount", "-t", "none", "-o", "defaults,bind",
                        "/home", path.Join(mountpoint, "/home"))
                call("mount", "-t", "none", "-o", "defaults,bind",
                        "/etc/resolv.conf", path.Join(mountpoint, "/etc/resolv.conf"))
                call("mount", "-t", "none", "-o", "defaults,bind",
                        "/tmp", path.Join(mountpoint, "tmp"))
                
                // makes mounpoint reusing possible
                err = os.Symlink(mountpoint, finalMountpoint)

                // its ok if the symlink was already generated by another process
                // we could cleanup the mounts at this point
                if ! os.IsExist(err){ check(err) }
        }

	pwd, err := os.Getwd(); check(err)
	err = syscall.Chroot(finalMountpoint); check(err)
        err = syscall.Setreuid(callerUid, callerUid); check(err)
	err = os.Chdir(pwd)
	if err != nil {
		err = os.Chdir("/"); check(err)
	}
	err = syscall.Exec("/usr/bin/env", os.Args[2:], os.Environ()); check(err)
}
