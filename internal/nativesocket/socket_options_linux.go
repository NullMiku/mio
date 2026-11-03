//go:build linux

package nativesocket

import "syscall"

func configureNoSigpipe(_ int) error { return nil }

func socketSend(fd int, data []byte) (int, error) {
	return syscall.SendmsgN(fd, data, nil, nil, syscall.MSG_NOSIGNAL)
}
