//go:build darwin

package nativesocket

import "syscall"

func configureNoSigpipe(fd int) error {
	return syscall.SetsockoptInt(fd, syscall.SOL_SOCKET, syscall.SO_NOSIGPIPE, 1)
}

func socketSend(fd int, data []byte) (int, error) {
	return syscall.Write(fd, data)
}
