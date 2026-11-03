//go:build windows

package nativesocket

import "Mio/mma"

// Windows' Winsock backend is not implemented yet. Keep unrelated Mio
// standard-library commands functional instead of failing registry setup.
func Register(_ *mma.ModuleRegistry) error { return nil }
